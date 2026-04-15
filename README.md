"""
The Quest — Level Editor
Reads/writes L00001.dat – L00007.dat map files and SAVE*.dat save files.

════════════════════════════════════════════════════════════════════
MAP FILE FORMAT  (L00001.dat – L00007.dat)
════════════════════════════════════════════════════════════════════
  100×100 tiles, 10 000 lines of 8 encoded fields each:
    x  y  floor  wall  object  enemy  gold  extra
  Numbers: each decimal digit stored as (digit + 0x81).
           Negative prefix: 0x7E byte before the digits.
  Fields delimited by 0x20 (space), lines by CRLF.

════════════════════════════════════════════════════════════════════
SAVE FILE FORMAT  (SAVE*.dat)  — confirmed by binary analysis
════════════════════════════════════════════════════════════════════
  Line 0        : 10 fields — field[0]=Player Level, field[1]=Class ID,
                  remaining fields are screen/position data (preserved verbatim).
                  Class IDs: 1=Knight  2=Mage  3=Rogue  4=Monk

  Lines 1–9999  : Map tile data, column-major order (same codec as map files).
                  Tile (1,1) is absent from this section.

  Lines 10000–10099 : Screen cache — 100 lines of 8 fields each:
                  [lx, ly, floor, wall, object, enemy, gold, extra]
                  lx/ly are 1-based coords within the current 10×10 screen block.

  Line 10100    : Player position — [abs_x, abs_y, rel_x, rel_y]

  Line 10101    : Player combat stats — 10 fields:
                  [0] Max Life   [1] Cur Life   [2] Max Mana   [3] Cur Mana
                  [4] Strength   [5] Intelligence [6] Dexterity [7] Accuracy
                  [8] Reputation [9] EXP Needed

  Line 10102    : Gold + potion counts — 12 fields:
                  [0–2] unknown (preserved verbatim)   [3] Gold
                  [4] Half Life Potion   [5] Full Life Potion
                  [6] Half Mana Potion   [7] Full Mana Potion
                  [8] Half Restoration   [9] Full Restoration
                  [10] Cure Poison       [11] Berserker Potion

  Lines 10103+  : World flags / inventory — preserved verbatim.

  Line 11358–11367 : Spell book LEFT column  — 10 spell slot IDs (0 = empty).
  Lines 11368–11387: Unknown gap             — never written, preserved verbatim.
  Lines 11388–11397: Spell book RIGHT column — 10 spell slot IDs (0 = empty).
  Lines 11398–11417: Spell learned flags     — 20 lines, one per spell ID (0/1).

  Line 11645    : Skill/Fault flags — 8 fields (each 0 or 1):
                  [0] Ambidexterity  [1] Bargaining  [2] Scholar
                  [3] Memorisation   [4] Markmanship
                  [5] Cowardice      [6] Honor        [7] Rashness

  Line 11649    : Skill/fault secondary encoding — preserved verbatim.
                  (Written by the game itself; exact format not fully decoded.)

SPELL IDs (lines 11358–11397 and 11398–11417):
   1=Heal            2=Flame           3=Teleport        4=Shield
   5=Ring of Ice     6=Black Ward      7=Invisibility    8=Summon Skeleton
   9=Inferno        10=Restore        11=Life Drain      12=Thunder Bolt
  13=Shield of Fire 14=Deteriorate   15=Summon Stone Knight
  16=Earthquake     17=Cure          18=Summon Scorpion
  19=Meteor         20=Dark Hour
"""
