# User settings for default *.rpp files

## Scope
- when creating temporary or permanent reaper files, use these default project settins
- do not apply these settings when opening a pre-existing *.rpp file

## Rules
- MUST: include these default settings, unless instructed otherwise or exceptions provided

## Required Reading
- works closely with **reaper-state-chunk-definitions.md** for full parameter definitions

## User default settings

### grid settings: no-snap
- set: GRID 3455 (no snap)
- not: GRID 3199 (snap)
- GRID 3455 is usually followed by seven digits: 8 1 8 1 0 0 0

### project settings: on import of media to project path
- set: after the line "DEFPITCHMODE 589824 0" set MISCOPTS 4
- this line isn't there unless this setting is set, so it includes ADDING a line, not editing.

