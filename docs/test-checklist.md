# FamilyHub test checklist (Nov 11, 2026)

Each test: **do this → you should see this.** Anything different → screenshot to Claude with the test number.
Already passed: wall update, routine files installed, phone room/thermostat pop-ups, porch cards,
phone doorbell video, sleep mode.

## Before you start (5 min)
- [ ] **0a. Alarm.com thermostat schedule**, both thermostats: Heat 67° 6 PM–9 AM, 60° 9 AM–6 PM; Cool 70° all day.
- [ ] **0b. Alarm.com: turn OFF the 4 outdoor light schedules** (Home Assistant runs them from tonight).

## Wall — adding things
- [x] **1. To-do +.** Lists page → To-Do **+** → a pop-up with Event / Chore / To-do / … opens on **To-do**.
      Type a title, pick a person, Add → pop-up closes, the to-do shows in the list with that person's colour.
- [x] **2. Calendar tap.** Week view → tap an empty slot (say Saturday 3 PM) → pop-up on **Event** with that
      date + 3:00 filled in. Tap **Chore** → the due date is still Saturday. Back to Event, add a title, Add →
      it appears on Saturday 3 PM.
- [x] **3. + Event button** (calendar header) → same pop-up, today's date.
- [x] **4. Festive keyboard.** Tap a text box → keyboard slides up. Keys type, ⇧ makes a capital, 123 shows
      numbers, return submits, **hide** puts it away, tapping outside the box puts it away.
- [x] **5. One keyboard only.** Pick one: Ubuntu Settings → Accessibility → Typing → Screen Keyboard **off**
      (keeps the festive one), or wall Settings → Display → uncheck the on-screen keyboard (keeps Ubuntu's).
      Then tap a text box → exactly one keyboard.

## Wall — house buttons (Home page)
- [ ] **6. Good night.** Tap → inside lights + TVs off, doors lock, alarm arms **Stay**, garage closes,
      floodlight off, porch/driveway stay on, wall says what it did and goes dark. Disarm to wake it.
- [ ] **7. Leaving.** (Leave a door open first.) Tap → lights incl. outdoor off, TVs off, locks, garage closes,
      wall says "Heads up: … is open" and **doesn't arm** while a door is open. Close it, tap again → arms Stay.
- [ ] **8. I'm home (alarm armed).** Tap → keypad "Welcome home". Correct code ✓ → alarm disarms, **then**
      garage opens, after dark porch/driveway/entry/kitchen lights on, wall says "Welcome home. I disarmed…".
- [ ] **9. I'm home — wrong code.** Arm, tap, enter a wrong code → alarm stays armed, **garage stays shut**,
      wall says the alarm didn't disarm.
- [ ] **10. I'm home (already disarmed).** No keypad; garage opens, lights after dark.

## Wall — cameras + doorbell
- [x] **11. Front door camera on the wall.** Home page → tap it → picture refreshes every few seconds, then
      **Live** with moving video; or after ~15 s+ "Live view isn't answering" + **Try live again**. Never a
      black screen saying Live.
- [ ] **12. Backyard camera on the wall** → goes Live.
- [ ] **13. Doorbell press.** Press the real button → wall pops the front camera + chimes + says someone's at
      the door; a Roku that's ON flashes the picture; both phones get a notification with the picture.

## Wall — status bar
- [x] **14. Door to garage.** Open the house→garage door → status bar says **"Door to garage open"**
      (not "Garage Door"). Close it → clears.
- [ ] **15. Leave-by.** Phone → Add → Event ~45 min from now with a **Where** (a real address) → within 2 min
      the wall's status bar shows a leave-by chip ("Leave in 20 min · 25 min drive"). At leave time the wall
      says "Time to leave".

## Wall — slideshow
- [ ] **16.** Phone → Settings → Photos → slideshow after **1 minute** → don't touch the wall for a minute →
      photos start; each stays the time you picked. Tap → back. Set it back to what you like.

## Phone — Automations (Settings → Automations)
- [ ] **17. Light lists.** Outdoor & holiday lights → Nightly / Holiday / Christmas window lights show the right
      names. Tap **Change** → checklist → add the **4th window plug** → **Done** → "Saved", name appears.
- [ ] **18. A setting.** Change "Holiday lights off / nightly lights on at" to a different time → "Saved";
      open "5 steps — what each one does" → the description shows the new time. Change it back.
- [ ] **19. New routine (2-minute test).** ＋ New routine → **A time** = 2 minutes from now → every day →
      **Say it on the wall** "Routine test" + **Notify our phones** "Routine test" → Save → "Routine saved".
      At that time the wall says it and both phones get it. It also shows in HA → Settings → Automations.
- [ ] **20. Edit + delete.** On that routine: Edit → change the message → Save. Then Edit → **Delete** → gone.
      (If Save says Home Assistant refused it → tell Claude: FamilyHub's HA login needs to be an admin.)
- [ ] **21. I'm home on the phone.** Same as test 8 but from the phone's Home tab (keypad pops up).

## Tonight + tomorrow (automatic — just look)
- [ ] **22. Sunset.** Porch, driveway and garage side-door lights come on by themselves (not holiday season yet).
      Settings → Automations → "Outdoor: sunset" says "last ran today …".
- [ ] **23. Sunrise.** They turn off.
- [ ] **24. 5 AM** pre-heat to 70°. **6 AM** both thermostats **off** (phone thermostat pop-up shows Off + the
      orange peak warning). **9 AM** back on (heat 60 / cool 70) in the mode they were in.
      Settings → Automations → Peak steps show "last ran today".

## Around the house
- [ ] **25. Rachell "away".** HA → Settings → People → Rachell → Track device = her phone. Her iPhone:
      Settings → Home Assistant → Location **Always** + **Precise**, Background App Refresh on → phone Home tab
      says "Alex, Rachell home".
- [ ] **26. Kwikset** 4× lithium AA. **27. Flaky door sensor** battery + magnet gap, test 5× at the panel.
- [ ] **28. Frame test corners** on the screen — tight / loose / any black showing, which edge.
