from collections import Counter
from pretty_midi import PrettyMIDI
import os
import json
import sqlite3
import numpy as np
import re

def identify_closest_chord(pitches):
    known_chords = {
        "Major": set([0, 4, 7]),
        "Minor": set([0, 3, 7]),
        "Diminished": set([0, 3, 6]),
        "Augmented": set([0, 4, 8])
    }
    
    min_distance = float('inf')
    closest_chord = "Unknown"
    
    for chord, chord_pitches in known_chords.items():
        distance = len(set(pitches) - chord_pitches) + len(chord_pitches - set(pitches))
        if distance < min_distance:
            min_distance = distance
            closest_chord = chord
    
    return closest_chord, min_distance if min_distance != 0 else 1

# Test the function
print(identify_closest_chord([0, 4, 7]))  # Should return 'Major', 1
print(identify_closest_chord([0, 4, 8]))  # Should return 'Augmented', 1
print(identify_closest_chord([2, 4, 6, 7, 11]))  # Should return 'Minor', 3 (or another chord based on distance)
    
def identify_mode_or_scale(pitches):
    major_scale = set([0, 2, 4, 5, 7, 9, 11])
    natural_minor_scale = set([0, 2, 3, 5, 7, 8, 10])
    # Add more scales or modes here

    if set(pitches) == major_scale:
        return "Major"
    elif set(pitches) == natural_minor_scale:
        return "Natural Minor"
    # Add more comparisons here

    return "Unknown"

def get_midi_files(directory):
    midi_files = []
    for filename in os.listdir(directory):
        if filename.endswith(".mid"):
            midi_files.append(os.path.join(directory, filename))
    return midi_files

def extract_chord_and_mode_from_filename(filename):
    # Using regex to extract the chord and mode (major or minor) from the file name
    match = re.search(r'([A-Ga-g]#?b?)(maj|min)', filename)
    if match:
        chord, mode = match.groups()
        return chord, mode
    else:
        return None, "Unknown"
    

def create_arp_table(conn):
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS ArpFeatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        key_signature TEXT,
        tempo REAL,
        time_signature TEXT,
        arpeggio_type TEXT,
        arpeggio_speed REAL,
        rhythmic_variation REAL,
        chord_outline TEXT,
        harmonic_complexity TEXT,
        melodic_peaks INTEGER,
        melodic_troughs INTEGER,
        mode_or_scale TEXT,
        syncopation_count INTEGER,
        total_notes INTEGER,
        unique_notes INTEGER,
        note_intervals TEXT
    )
    ''')
    conn.commit()

def analyze_arp_midi_enhanced(midi_file_path):
    try:
        midi_data = PrettyMIDI(midi_file_path)
    except Exception as e:
        print(f"Error reading {midi_file_path}: {e}")
        return None

    features = {'arp_type': 'No Arp'}  # Initialize with a default value for 'arp_type'
    first_instrument = None

    # Extracting tempo from file name
    if features:  # Make sure features dictionary is not empty
        features['file_name'] = os.path.basename(midi_file_path)  # Add this line

        # Extracting tempo from filename
        tempo_match = re.search(
            r'(\d+)\s*bpm\b', features['file_name'], re.IGNORECASE)
        if tempo_match:
            features['tempo'] = int(tempo_match.group(1))
        else:
            # Split by non-digits and filter out short numerical sequences
            potential_tempos = [int(x) for x in re.split(
                r'\D+', features['file_name']) if x.isdigit() and int(x) > 40]
            if potential_tempos:
                # Use the first valid tempo found
                features['tempo'] = potential_tempos[0]
            else:
                # If no valid tempo information is found, set tempo to "unknown"
                features['tempo'] = "unknown"

    # Extracting time signature from MIDI data
    if midi_data.time_signature_changes:
        first_time_signature = midi_data.time_signature_changes[0]
        features['time_signature'] = f"{first_time_signature.numerator}/{first_time_signature.denominator}"
    else:
        features['time_signature'] = None

    for instrument in midi_data.instruments:
        if not instrument.is_drum and instrument.notes:
            first_instrument = instrument
            break

    if first_instrument:
        pitch_sequence = [note.pitch for note in first_instrument.notes]
        ascending_count = 0
        descending_count = 0
        for i in range(len(pitch_sequence) - 1):
            if pitch_sequence[i] < pitch_sequence[i + 1]:
                ascending_count += 1
            elif pitch_sequence[i] > pitch_sequence[i + 1]:
                descending_count += 1

        if ascending_count > descending_count:
            features['arp_type'] = 'Ascending'
        elif descending_count > ascending_count:
            features['arp_type'] = 'Descending'
        else:
            features['arp_type'] = 'Random'
        
        note_intervals = [note.end - note.start for note in first_instrument.notes]
        features['arpeggio_speed'] = np.mean(note_intervals)

        unique_pitches = list(set([note.pitch % 12 for note in first_instrument.notes]))
        print("Debug: unique_pitches:", unique_pitches)  # Debugging line here
        features['chord_outline'] = unique_pitches

       # Harmonic Complexity:
        chord_name, complexity = identify_closest_chord(unique_pitches)
        features['harmonic_complexity'] = {
            'chord': chord_name,
            'complexity': complexity
        }

        features['total_notes'] = len(first_instrument.notes)
        features['unique_notes'] = len(unique_pitches)

        pitch_sequence = [note.pitch for note in first_instrument.notes]
        features['note_intervals'] = [pitch_sequence[i] - pitch_sequence[i-1] for i in range(1, len(pitch_sequence))]

        features['rhythmic_variation'] = np.std(note_intervals)

        peaks = 0
        troughs = 0
        for i in range(1, len(pitch_sequence) - 1):
            if pitch_sequence[i] > pitch_sequence[i-1] and pitch_sequence[i] > pitch_sequence[i+1]:
                peaks += 1
            elif pitch_sequence[i] < pitch_sequence[i-1] and pitch_sequence[i] < pitch_sequence[i+1]:
                troughs += 1
        features['melodic_peaks'] = peaks
        features['melodic_troughs'] = troughs

        features['mode_or_scale'] = identify_mode_or_scale(unique_pitches)

        syncopation_count = 0
        for note in first_instrument.notes:
            if round(note.start) % 4 in [1, 3]:
                syncopation_count += 1
        features['syncopation_count'] = syncopation_count

    else:
        features['arp_type'] = 'No Arp'

    return features

def insert_into_db(features, key_signature, conn, table_name):
    c = conn.cursor()
    if table_name == 'ArpFeatures':
        print(f"Debug: values before DB insertion: {features.get('arp_type', None)}")  # Debug print
        c.execute(f"INSERT INTO {table_name} (file_name, key_signature, tempo, time_signature, arpeggio_type, arpeggio_speed, rhythmic_variation, chord_outline, harmonic_complexity, melodic_peaks, melodic_troughs, mode_or_scale, syncopation_count, total_notes, unique_notes, note_intervals) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (features['file_name'], key_signature, features.get('tempo', None), features.get('time_signature', None), features.get('arp_type', None), features.get('arpeggio_speed', None), features.get('rhythmic_variation', None), json.dumps(features.get('chord_outline', None)), json.dumps(features.get('harmonic_complexity', None)), features.get('melodic_peaks', None), features.get('melodic_troughs', None), features.get('mode_or_scale', None), features.get('syncopation_count', None), features.get('total_notes', None), features.get('unique_notes', None), json.dumps(features.get('note_intervals', None))))
    conn.commit()

def main():
    root_folder = '/Users/ZoesComputer/Desktop/Zoe Midi/test'
    conn = sqlite3.connect('midi_features.db')
    create_arp_table(conn)
    for key_folder in os.listdir(root_folder):
        key_path = os.path.join(root_folder, key_folder)
        if os.path.isdir(key_path):
            inst_path = os.path.join(key_path, 'Arp')
            if os.path.exists(inst_path):
                for midi_file in get_midi_files(inst_path):
                    features = analyze_arp_midi_enhanced(midi_file)  # Note: Changed to the enhanced function
                    if features:
                        features['file_name'] = os.path.basename(midi_file)  # Add this line

                        # Extract chord and mode from the filename
                        chord, mode = extract_chord_and_mode_from_filename(os.path.basename(midi_file))
                        features['mode_or_scale'] = mode if mode else "Unknown"

                        print(f"Debug: features before insertion: {features}")  # Debug print statement
                        insert_into_db(features, key_folder, conn, 'ArpFeatures') 

    conn.commit()
    conn.close()

# Uncomment the following line to run the main function
if __name__ == "__main__":
     main()
