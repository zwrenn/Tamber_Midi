import sqlite3

# Initialize SQLite database
conn = sqlite3.connect('midi_features.db')
c = conn.cursor()

# Create table
c.execute('''
    CREATE TABLE IF NOT EXISTS BassFeatures(
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
        harmony_complexity INTEGER,
        melodic_range INTEGER,
        rhythmic_variability REAL,
        root_note_consistency REAL,
        note_repetition REAL,
        harmonic_tension INTEGER,
        interval_distribution TEXT,
        rhythmic_motifs TEXT,
        instrumentation TEXT,
        melodic_direction TEXT,
        motivic_development TEXT,
        mode TEXT,
        syncopation INTEGER,
        polyphonic_density INTEGER,
        dynamics TEXT,
        rhythmic_complexity TEXT,
        melodic_contour TEXT,
        root_notes TEXT,
        duration REAL
    )
    ''')

conn.commit()
conn.close()
