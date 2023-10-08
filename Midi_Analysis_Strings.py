from pretty_midi import PrettyMIDI
import os
import sqlite3
from collections import Counter

def find_repetitive_patterns(melodic_intervals, min_length=3):
    counter = Counter()
    for i in range(len(melodic_intervals)):
        for j in range(i + min_length, len(melodic_intervals) + 1):
            motif = tuple(melodic_intervals[i:j])
            counter[motif] += 1
    return [(item, count) for item, count in counter.items() if count > 1]


def analyze_string_midi(midi_file_path):
    try:
        midi_data = PrettyMIDI(midi_file_path)
    except Exception as e:
        print(f"Error reading {midi_file_path}: {e}")
        return None

    features = {}
    first_instrument = None

    for instrument in midi_data.instruments:
        if not instrument.is_drum and instrument.notes:
            first_instrument = instrument
            break

    if first_instrument:
        # Vibrato Patterns (Placeholder for now)
        # Initialize a list to hold the pitch bend events for the first instrument
        pitch_bends = first_instrument.pitch_bends

        # Initialize a variable to hold the number of vibrato patterns
        num_vibrato_patterns = 0

        # ---- Your new Vibrato analysis code starts here ----
        
        # Check if there are any pitch bend events
        if pitch_bends:
            # Sort the pitch bend events by time
            pitch_bends.sort(key=lambda x: x.time)
            
            # Initialize variables to hold the state of the pitch bend
            last_pitch = None
            current_streak = 0
            
            # Loop through each pitch bend event
            for bend in pitch_bends:
                # Check if this pitch bend continues a streak of oscillating bends
                if last_pitch is not None and bend.pitch != last_pitch:
                    current_streak += 1
                else:
                    # If the streak has ended, check if it was long enough to be considered a vibrato
                    if current_streak > 2:
                        num_vibrato_patterns += 1
                    
                    # Reset the streak
                    current_streak = 0
                
                # Update the last pitch
                last_pitch = bend.pitch

        # Add the number of vibrato patterns to the features dictionary
        features['vibrato_patterns'] = num_vibrato_patterns

        # Legato vs Staccato
        note_durations = [note.end - note.start for note in first_instrument.notes]
        legato_count = sum(1 for duration in note_durations if duration > 0.5)
        staccato_count = len(note_durations) - legato_count

        if legato_count > 0 and staccato_count == 0:
            legato_ratio = "Only Legato"
        elif legato_count == 0 and staccato_count > 0:
            legato_ratio = "Only Staccato"
        elif legato_count == 0 and staccato_count == 0:
            legato_ratio = "No Notes"
        else:
            legato_ratio = legato_count / staccato_count

        # Melodic Intervals
        pitch_sequence = [note.pitch for note in first_instrument.notes]
        melodic_intervals = [abs(pitch_sequence[i] - pitch_sequence[i - 1]) for i in range(1, len(pitch_sequence))]

        # Find Repetitive Patterns
        repetitive_patterns = find_repetitive_patterns(melodic_intervals)
        features['repetitive_patterns'] = repetitive_patterns

        # Compute Note Density
        total_notes = len(first_instrument.notes)
        total_time = midi_data.get_end_time()
        note_density = total_notes / total_time
        features['note_density'] = note_density

        # Polyphony
        start_times = [note.start for note in first_instrument.notes]
        print(f"Debug: Start times: {start_times}")  # Debugging line
        is_polyphonic = 'Yes' if len(first_instrument.notes) > len(set(note.start for note in first_instrument.notes)) else 'No'
        
        # Dynamic Range
        velocities = [note.velocity for note in first_instrument.notes]
        dynamic_range = max(velocities) - min(velocities)

        features.update({
            'vibrato_patterns': num_vibrato_patterns,
            'legato_ratio': legato_ratio,
            'melodic_intervals': melodic_intervals,
            'is_polyphonic': is_polyphonic,
            'dynamic_range': dynamic_range
        })
    else:
        features['instrument_type'] = 'No String'

    return features


def get_midi_files(directory):
    midi_files = []
    for filename in os.listdir(directory):
        if filename.endswith(".mid"):
            midi_files.append(os.path.join(directory, filename))
    return midi_files

def create_string_table(conn):
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS StringFeatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        vibrato_patterns INTEGER,
        legato_ratio REAL,
        melodic_intervals TEXT,
        is_polyphonic TEXT,
        dynamic_range INTEGER,
        repetitive_patterns TEXT,
        note_density REAL
    )
    ''')
    conn.commit()

def insert_into_db(features, conn, table_name):
    c = conn.cursor()
    c.execute(f"INSERT INTO {table_name} (file_name, vibrato_patterns, legato_ratio, melodic_intervals, is_polyphonic, dynamic_range, repetitive_patterns, note_density) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (features['file_name'], features.get('vibrato_patterns', None), features.get('legato_ratio', None), str(features.get('melodic_intervals', None)), features.get('is_polyphonic', None), features.get('dynamic_range', None), str(features.get('repetitive_patterns', None)), features.get('note_density', None)))
    conn.commit()

def main():
    root_folder = '/Users/ZoesComputer/Desktop/Zoe Midi/test'  # Pointing to the root folder
    conn = sqlite3.connect('midi_features.db')
    create_string_table(conn)
    for key_folder in os.listdir(root_folder):
        key_path = os.path.join(root_folder, key_folder)
        if os.path.isdir(key_path):
            inst_path = os.path.join(key_path, 'String')  # Looking for the 'String' folder
            if os.path.exists(inst_path):
                for midi_file in get_midi_files(inst_path):
                    features = analyze_string_midi(midi_file)  # Using the correct function
                    if features:
                        features['file_name'] = os.path.basename(midi_file)
                        print(f"Debug: features before insertion: {features}")  # Debug print statement
                        insert_into_db(features, conn, 'StringFeatures')  # Correct arguments

    conn.commit()
    conn.close()

# Uncomment the following line to run the main function
if __name__ == "__main__":
    main()