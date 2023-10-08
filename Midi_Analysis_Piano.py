from music21 import converter
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


def analyze_midi(midi_file_path):
    try:
        midi_data = PrettyMIDI(midi_file_path)
    except:
        print(f"Error reading {midi_file_path}")
        return None

    features = {}

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
    features['harmony_complexity'] = len(set(root_notes))

    # Extracting pitch classes
    features['pitch_classes'] = features.get('root_notes', None)

    # Chord Progression Analysis using Music21
    midi = converter.parse(midi_file_path)
    chord_progression = []
    for thisChord in midi.recurse().getElementsByClass('Chord'):
        chord_name = thisChord.pitchedCommonName
        # Assuming the duration is stored in quarter lengths
        chord_duration = thisChord.duration.quarterLength
        chord_progression.append((chord_name, chord_duration))
    features['chord_progression'] = chord_progression

    # Melodic Contour
    # For simplicity, taking the first instrument's notes
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
            pitch_changes = []
            for i in range(1, len(first_instrument.notes)):
                pitch_changes.append(
                    first_instrument.notes[i].pitch - first_instrument.notes[i-1].pitch)
            features['melodic_contour'] = Counter(pitch_changes)

    # Rhythmic Complexity
    # Counting the unique note durations for the first instrument
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
            note_durations = []
            for note in first_instrument.notes:
                note_durations.append(note.end - note.start)
            features['rhythmic_complexity'] = Counter(note_durations)

    # Dynamics
    # Velocity changes in the first instrument
    if midi_data.instruments:
        first_instrument = midi_data.instruments[0]
        if first_instrument.notes:
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

    return features


def create_db():
    conn = sqlite3.connect('midi_features.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS PianoFeatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        key_signature TEXT,
        total_notes INTEGER,
        unique_notes INTEGER,
        note_length_mean REAL,
        note_length_std REAL,
        velocity_mean REAL,
        velocity_std REAL,
        start_time_mean REAL,
        start_time_std REAL,
        end_time_mean REAL,
        end_time_std REAL,
        pitch_classes TEXT,
        chord_progression TEXT,
        tempo REAL,
        time_signature TEXT,
        key_scale TEXT,
        modality TEXT,
        harmony_complexity INTEGER
    )
    ''')
    conn.commit()
    conn.close()


def insert_into_db(features, key_signature, conn, table_name='PianoFeatures'):
    c = conn.cursor()
    key_scale, modality = key_signature.split('_')

    # Convert potentially fractional values to float
    note_length_mean = float(features.get('note_length_mean', None))
    note_length_std = float(features.get('note_length_std', None))
    start_time_mean = float(features.get('start_time_mean', None))
    start_time_std = float(features.get('start_time_std', None))
    end_time_mean = float(features.get('end_time_mean', None))
    end_time_std = float(features.get('end_time_std', None))

    # Convert chord progression and pitch classes to string (if they are not already)
    chord_progression = [str(chord)
                         for chord in features.get('chord_progression', [])]

    pitch_classes_dict = features.get('pitch_classes', {})
    pitch_classes = {str(k): str(v) for k, v in pitch_classes_dict.items(
    )} if pitch_classes_dict is not None else {}

    c.execute(f"INSERT INTO {table_name} (file_name, key_signature, total_notes, unique_notes, note_length_mean, note_length_std, velocity_mean, velocity_std, start_time_mean, start_time_std, end_time_mean, end_time_std, pitch_classes, chord_progression, tempo, time_signature, key_scale, modality, harmony_complexity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (features['file_name'], key_signature, features.get('total_notes', None), features.get('unique_notes', None), note_length_mean, note_length_std, features.get('velocity_mean', None), features.get('velocity_std', None), start_time_mean, start_time_std, end_time_mean, end_time_std, json.dumps(pitch_classes), json.dumps(chord_progression), features.get('tempo', None), features.get('time_signature', None), key_scale, modality, features.get('harmony_complexity', None)))

def main():
    create_db()
    root_folder = '/Users/ZoesComputer/Desktop/Zoe Midi/test'
    conn = sqlite3.connect('midi_features.db')
    for key_folder in os.listdir(root_folder):
        key_path = os.path.join(root_folder, key_folder)
        if os.path.isdir(key_path):
            for inst_folder in ['Piano', 'Keys']:  # Adding a loop to go through both 'Piano' and 'Keys'
                inst_path = os.path.join(key_path, inst_folder)
                if os.path.exists(inst_path):
                    for midi_file in get_midi_files(inst_path):
                        features = analyze_midi(midi_file)
                        if features:
                            insert_into_db(features, key_folder, conn, 'PianoFeatures')  # Storing both in 'PianoFeatures'
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()

