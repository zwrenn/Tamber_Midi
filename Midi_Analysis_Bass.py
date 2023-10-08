from music21 import converter, scale, pitch
from collections import Counter
from pretty_midi import PrettyMIDI
import os
import json
import sqlite3
import numpy as np
import re

def get_midi_files(directory):
    midi_files = []
    for filename in os.listdir(directory):
        if filename.endswith(".mid"):
            midi_files.append(os.path.join(directory, filename))
    return midi_files

def create_bass_table(conn):
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS BassFeatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        key_signature TEXT,
        tempo REAL,
        time_signature TEXT,
        rhythmic_complexity TEXT,
        pitch_classes TEXT,
        total_notes INTEGER,
        unique_notes INTEGER,
        note_intervals TEXT,
        scale_usage TEXT,
        syncopation REAL,
        groove_patterns TEXT,
        rest_durations TEXT,
        harmonic_role TEXT,
        motivic_development TEXT
    )
    ''')
    conn.commit()

def analyze_bass_midi(midi_file_path):
    try:
        midi_data = PrettyMIDI(midi_file_path)
    except Exception as e:
        print(f"Error reading {midi_file_path}: {e}")
        return None

    features = {}
    first_instrument = None  # Initialize first_instrument to None

    print("Analyzing:", midi_file_path)
    # Basic Information
    features['file_name'] = os.path.basename(midi_file_path)
    features['duration'] = midi_data.get_end_time()

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

    # Harmony and Melody Analysis using PrettyMIDI
    root_notes = []
    for instrument in midi_data.instruments:
        if not instrument.is_drum:
            notes_playing = [note.pitch for note in instrument.notes]
            if len(notes_playing) >= 3:
                root_note = min(notes_playing)
                root_notes.append(root_note % 12)
    features['root_notes'] = Counter(root_notes)

    # Extracting pitch classes
    features['pitch_classes'] = features.get('root_notes', None)

    # Chord Progression Analysis using Music21
    midi = converter.parse(midi_file_path)
    chord_progression = []
    for thisChord in midi.recurse().getElementsByClass('Chord'):
        chord_name = thisChord.pitchedCommonName
        chord_duration = thisChord.duration.quarterLength
        chord_progression.append((chord_name, chord_duration))
    features['chord_progression'] = chord_progression

    # Initialize first_instrument to None
    first_instrument = None

    # Determine the first non-drum instrument with notes
    for instrument in midi_data.instruments:
        if not instrument.is_drum and instrument.notes:
            first_instrument = instrument
            break

    # Check if first_instrument is not None and has notes
       # Debug: Print first_instrument and its notes
    print("First Instrument:", first_instrument)
    if first_instrument:
        print("First Instrument Notes:", first_instrument.notes)
        # Melodic Contour
        pitch_changes = []
        for i in range(1, len(first_instrument.notes)):
            pitch_changes.append(
                first_instrument.notes[i].pitch - first_instrument.notes[i-1].pitch)
        features['melodic_contour'] = Counter(pitch_changes)

        # Rhythmic Complexity
        note_durations = [note.end - note.start for note in first_instrument.notes]
        features['rhythmic_complexity'] = Counter(note_durations)

        # Dynamics
        velocities = [note.velocity for note in first_instrument.notes]
        features['dynamics'] = Counter(velocities)

    # Polyphonic Density
    # Number of notes playing at the same time
    if midi_data.instruments:
        polyphony = []
        for instrument in midi_data.instruments:
            if not instrument.is_drum:
                polyphony.extend([(note.start, note.end)
                                 for note in instrument.notes])
        polyphony.sort(key=lambda x: x[0])
        max_notes = 0
        current_notes = 0
        current_time = 0
        for start, end in polyphony:
            while polyphony and polyphony[0][1] <= start:
                current_notes -= 1
                polyphony.pop(0)
            current_notes += 1
            max_notes = max(max_notes, current_notes)
        features['polyphonic_density'] = max_notes

        # Additional features (You do not have to remove the existing ones)
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
            total_notes = len(first_instrument.notes)
            unique_notes = len(
                set([note.pitch for note in first_instrument.notes]))
            note_lengths = [note.end -
                            note.start for note in first_instrument.notes]
            note_length_mean = np.mean(note_lengths)
            note_length_std = np.std(note_lengths)
            velocities = [note.velocity for note in first_instrument.notes]
            velocity_mean = np.mean(velocities)
            velocity_std = np.std(velocities)
            start_times = [note.start for note in first_instrument.notes]
            end_times = [note.end for note in first_instrument.notes]

            # Add them to the features dictionary
            features['total_notes'] = total_notes
            features['unique_notes'] = unique_notes
            features['note_length_mean'] = note_length_mean
            features['note_length_std'] = note_length_std
            features['velocity_mean'] = velocity_mean
            features['velocity_std'] = velocity_std
            features['start_time_mean'] = np.mean(start_times)
            features['start_time_std'] = np.std(start_times)
            features['end_time_mean'] = np.mean(end_times)
            features['end_time_std'] = np.std(end_times)

    # Adding new features
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
            # Note Intervals
            notes = [note.pitch for note in first_instrument.notes]
            note_intervals = [notes[i] - notes[i - 1] for i in range(1, len(notes))]
            features['note_intervals'] = note_intervals

            # Rest Durations
            rest_durations = [first_instrument.notes[i].start - first_instrument.notes[i - 1].end for i in range(1, len(first_instrument.notes))]
            features['rest_durations'] = rest_durations

    # 1. Note Intervals
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
            note_intervals = []
            for i in range(1, len(first_instrument.notes)):
                note_intervals.append(first_instrument.notes[i].pitch - first_instrument.notes[i-1].pitch)
            features['note_intervals'] = note_intervals

    # 2. Scale Usage (moved the scale_counter initialization outside the if block)
    scale_counter = {}
    print("Calculating scale usage...")
    if first_instrument and first_instrument.notes:
        all_pitches = [note.pitch % 12 for note in first_instrument.notes]
    else:
        all_pitches = []  # Making sure all_pitches is an empty list if first_instrument or its notes are None

    # Loop through each scale type
    for sc in ['major', 'minor', 'dorian', 'mixolydian', 'lydian', 'phrygian', 'locrian']:
        # Create a scale object based on the scale type
        if sc == 'major':
            this_scale = scale.MajorScale()
        elif sc == 'minor':
            this_scale = scale.MinorScale()
        elif sc == 'dorian':
            this_scale = scale.DorianScale()
        elif sc == 'mixolydian':
            this_scale = scale.MixolydianScale()
        elif sc == 'lydian':
            this_scale = scale.LydianScale()
        elif sc == 'phrygian':
            this_scale = scale.PhrygianScale()
        elif sc == 'locrian':
            this_scale = scale.LocrianScale()

        # Initialize a counter for the number of notes that belong to this scale
        scale_notes = 0

        # Check each pitch in all_pitches to see if it belongs to this scale
        for p in all_pitches:
            if p in [p.midi % 12 for p in this_scale.getPitches('C4', 'C5')]:
                scale_notes += 1

        # Add the count of scale notes to the scale_counter dictionary
        scale_counter[sc] = scale_notes

    # Add the scale_counter dictionary to the features dictionary
    features['scale_usage'] = scale_counter


    print("Calculating syncopation...")
    if first_instrument and first_instrument.notes:  # Check for None and empty notes
        syncopation_count = sum(1 for note in first_instrument.notes if note.start % 1 > 0.5)
        features['syncopation_count'] = syncopation_count
    else:
        features['syncopation_count'] = None

    print("Calculating groove patterns...")
    if first_instrument and first_instrument.notes:  # Check for None and empty notes
        rhythmic_patterns = [note.end - note.start for note in first_instrument.notes]
        features['groove_patterns'] = Counter(rhythmic_patterns)
    else:
        features['groove_patterns'] = None

    print("Calculating rest durations...")
    if first_instrument and first_instrument.notes:  # Check for None and empty notes
        note_objects = first_instrument.notes
        rest_durations = [note_objects[i + 1].start - note_objects[i].end for i in range(len(note_objects) - 1)]
        features['rest_durations'] = rest_durations
    else:
        features['rest_durations'] = None

    print("Calculating harmonic role...")
    if first_instrument and first_instrument.notes:  # Check for None and empty notes
        features['harmonic_role'] = Counter([note.pitch % 12 for note in first_instrument.notes])
    else:
        features['harmonic_role'] = None

    print("Calculating motivic development...")
    if first_instrument and first_instrument.notes:  # Check for None and empty notes
        notes = [note.pitch for note in note_objects]
        potential_motifs = [tuple(notes[i:i+3]) for i in range(len(notes) - 2)]
        features['motivic_development'] = Counter(potential_motifs)
    else:
        features['motivic_development'] = None

    # Convert keys to strings for JSON serialization
    if features['harmonic_role']:
        features['harmonic_role'] = {str(k): v for k, v in features['harmonic_role'].items()}
    if features['motivic_development']:
        features['motivic_development'] = {str(k): v for k, v in features['motivic_development'].items()}

    return features

def insert_into_db(features, key_signature, conn, table_name):
    c = conn.cursor()
    if table_name == 'BassFeatures':
        c.execute(f"INSERT INTO {table_name} (file_name, key_signature, tempo, time_signature, rhythmic_complexity, pitch_classes, total_notes, unique_notes, note_intervals, scale_usage, syncopation, groove_patterns, rest_durations, harmonic_role, motivic_development) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (features['file_name'], key_signature, features.get('tempo', None), features.get('time_signature', None), json.dumps(features.get('rhythmic_complexity', None)), json.dumps(features.get('pitch_classes', None)), features.get('total_notes', None), features.get('unique_notes', None), json.dumps(features.get('note_intervals', None)), json.dumps(features.get('scale_usage', None)), features.get('syncopation_count', None), json.dumps(features.get('groove_patterns', None)), json.dumps(features.get('rest_durations', None)), json.dumps(features.get('harmonic_role', None)), json.dumps(features.get('motivic_development', None))))
    conn.commit()

def main():
    root_folder = '/Users/ZoesComputer/Desktop/Zoe Midi/test'
    conn = sqlite3.connect('midi_features.db')
    create_bass_table(conn)

    for key_folder in os.listdir(root_folder):
        key_path = os.path.join(root_folder, key_folder)
        if os.path.isdir(key_path):
            inst_path = os.path.join(key_path, 'Bass')
            if os.path.exists(inst_path):
                for midi_file in get_midi_files(inst_path):
                    features = analyze_bass_midi(midi_file)
                    if features:
                        insert_into_db(features, key_folder, conn, 'BassFeatures')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
