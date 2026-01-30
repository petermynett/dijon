# DIJON PROJECT REPORT

## Project Description

This project explores how musical form and harmony (supported by melody), can be analyzed using techniques from music information retrieval.

It will create different ways to visualize harmony and form and compare different performances of a single song, as well as comparisons across different sets of songs.

The genres of jazz and bluegrass will be used so that lead sheets can be used as truth for a larger set of meaningfully varied performances. This will allow for an easy to produce large set of partially labelled data.

These tools could support musicians in grouping related pieces to study improvisational strategies across subtly different harmonic and formal structures, and could also assist researchers by providing computational structure and visual context where detailed musical intuition may be limited.

## Research Goals

Design a scalable, reproducible MIR pipeline that uses computational similarity, clustering, and visualization to support exploratory, explanatory, and evaluative analysis of form and harmony in variable musical repertoires.

It attempts to potentially answer some of the following questions:
- Which are the most unique performances of a song?
    - most different harmonic intepretations
    - deviation in form or meter
    - harmonic or formal variance between head (or standard form) and solos
- What songs share similar formal or harmonic characteristics?
- Are there new and interesting ways to visualize harmony and form?


## Data Pipeline

**Acquisition → Raw:** Sources acquire external artifacts into `acquisition/`. The pipeline ingests them into `raw/`, which is the canonical level.

**Annotations layer on top:** Annotations represent manual judgments and accumulate alongside automated outputs. They are an added canonical layer alongside raw.

**Database and notebooks consume:** The database indexes filesystem data for querying. Notebooks perform exploratory analysis without modifying the core pipeline.

### Further Potential Annotations
- formal markers: done
- head in/out: for exact form and bar:beat comparison
- song features: key signatures, time signatures, style/genre, instrumentation
- bass lines ?? (just because it won't take me tooooo long to do them)

## Tools

- Python (major)
- SQL (minor? tbd)
- Main IDE: Cursor
- Jupyter notebooks with Google Colab

### External Apps
- Reaper: used to label formal markers
- Musescore: used to label chord progressions and other song features (time signature, key signature)
- 

### Non-trivial packages
- ffmpeg
- librosa
- numpy
- scipy
- pysoundfile
- numba
- mir_eval
- music21
- scikit-learn
- pandas
- matplotlib
- ipywidgets
- jupyterlab
- notebook
- ipykernel
- ??

## Current Questions

### Project Structure
- Is the package design correct for this project?
- are there any specs or requirements to review for the written reports? What else would this file need to include? 

### Data
- How to use the database effectively? Is the db necessary or is there a place for it?
- How to ensure that the raw layer is strong
- Are notebook artifacts canonical or ephemeral? 

### Jupyter Notebooks
- Google Colab for notebooks is not yet implemented
- Notebooks not yet developed

### MISC
- testings
- logs