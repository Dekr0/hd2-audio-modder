- Mod (field I understand so far)
    - game_archives: dict[str, GameArchive]
        - str -> basename of a game archive
        - GameArchive -> an object that encapsulate a game archive file
    - wwise_banks: dict[int, WwiseBank]
        - int -> 128 bit resource ID of a soundbank in a game archive file
        - WwiseBank -> an object that encapsulate a soundbank
    - bank_count: dict[int, int]
        - int -> 128 bit resource ID of a soundbank
        - int -> # of times a soundbank with a 128 bit resource ID appear in a Mod object
            - This is an side effect due to fact of which a soundbank can occur in 
             different game archives
    - audio_sources: dict[int, AudioSource]
        - int -> 32 bit source ID (not 32 bit hierarchy object ID) of an audio source
        - AudioSource -> an object that encapsulate an audio source
    - audio_count: dict[int, int]
        - int -> 32 bit source ID (not 32 bit hierarchy object ID) of an audio source
        - int -> # of times an audio source with a 32 bit source ID appear in a Mod object
            - This is an side effect due to the fact of which an audio source can be shared 
            in different soundbanks, and the fact of which an audio source is only used in 
            soundbank but that soundbank appear in different game archives.

- Side Effect Scneario
    - Archive A with a single soundbank 
    - When both two archives (A and B) contains a single soundbank with the same 128 bits 
     resource ID (resource_id_a), given 
        - Increment # of times a soundbank with resource ID (resource_id_a) appear in 
         the current Mod object.
        - For each audio source object in archive B, 
        - Replace the WwiseBank with resource ID (resource_id_a) in the new loaded archives 
        with the one currently store in the current Mod object. 
            - Why though?
            - This make mutation harder to reason about