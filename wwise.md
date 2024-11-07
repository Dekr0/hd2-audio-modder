## Wwise: Introduction

- Audiokinetic Wwise is audio engine 
  - with DAW features that handles game audio,
  - ...

- Audiokinetic Wwise integrates with standard C++ gamesas well as common game 
engines (Unity, Unreal Engine 4, etc.), through its dedicated API.

- The Wwise approach to builidng and integrating audio in a game includes five 
main components:
  - **Audio Structures**  
  - **Events**
  - **Game Syncs** 
  - **Game Objects** 
  - **Listeners** 

- Audio structures represent the individual sounds in a game created and managed 
within the **Wwise application**.

- Game objects and Listeners represent specific game elements that **emit** or 
**receive** audio.
- These are created and managed within **a game**.

- Events and Game Syncs are used to **drive** the audio in a game.
- These two components create a bridge between the audio assest and game components.
- These two components are integral to both Wwise and a game.

## Wwise: Project Hirearchy

### Actor-Mixer Hierarchy

- This type of hierarchy groups and organized all the **sound** and **motion** 
assets in a project.

- Actor-Mixer Hierarchy use the concept of object for organization.

- Common types of objects:
    - Sound objects
    - Motion FX objects
    - Containers
        - Random
        - Sequence
    - Actor-Mixer

- The base (leaf node) of a hierarchy are individual **sound objects** and 
**motion objects**.
- They cannot be a parent / root of other types of objects.
- Each object (both sound and motion) have its own properties and behaviors. 
    - Properties: volume, pitch, positioning, ...
    - Behaviors: random playback, sequence playback, ...

- Objects (all types of objects) can be grouped as a **unit**.
- Change in properties and behaviors in a **unit** affect properties and behaviors 
of each object in that unit.

#### Sound Object

- Wwise use this to represent voice and SFX assets in a game.

```
*--------------*    *--------------*    *------------*
| Sound Object | -> | Audio Source | -> | Audio File |
*--------------*    *--------------*    *------------*
```

#### Building a Hierarchy of Audio Structures

- Containers are used to group soud objects within a project.
- They can play a group objects according to a certain behavior, such as Random, 
Sequence, Switch, and so on.

### Interactive Music Hierarchy (For music)

- Skipped

### Master-Mixer Hierarchy

- This type of hierarchy sits on top of Actor-Mixer and Interactive Music 
hierarch**ies**.

- This type of hierarchy can re-group and mix many different sound, music, and 
motion structures within a project and prepare them for output.

#### A brief walk through of traditional mixing techniques in a typical DAW

- There are different instructments.
- They are routed to a **bus**.
- Their sound properties can be control as a single mixed sound.

- The Master-Mixer hierarchy is divied into two sectiosn:
    1. sound and music
    2. motion
- Each section consists of a top-level "Master Bus" and any number of **child** 
busses below it.

- Sound, music, and motion structures can be routed through these busses using 
the main categories within a game.
- Example categories
    - Voice
    - Ambience
    - Sound Effects
    - Music

## Wwise: Event

- Wwise uses **Events** to drive the audio in a game.

- Events apply actions to the different **sound objects** , or **object groups** 
in a project hierarch.

- An action specify whether a Wwise objects will play, stop, pause, and so on.

- There are two types of action **Events**:
    - "Action" Events - use one of more actions, such as play, stop, pause and 
    so on, to **drive** the sound, music, and motion in game.
    - "Dialogue" Events - use a type of decision tree with **States** and 
    **Switches** to dynamically determine what object is played.

- After Events are created in Wwise, the can be integrated into the game engine 
so that they are called at the appropriate times in the game.
