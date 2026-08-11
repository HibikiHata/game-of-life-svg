"""365 days of contribution levels taken from a real calendar (2026-08-10).

**Uniform random data cannot stand in for this.** Measured the same day, a
uniformly random board at the same density (120/365) *grows* from 120 to 136
live cells under the standard rule, while this sequence collapses from 120
to 24.

The reason is runs of consecutive active days. A GitHub calendar stacks
weekdays vertically and wraps by week, so **a run of active days extends down a
column and forms a dense rectangle**. The run-length distribution here is
{1: 9, 2: 3, 3: 1, 5: 1, 18: 1, 33: 1, 46: 1} — runs of 46, 33 and 18 days. The
46-day run fills roughly seven rows by seven columns, and the cells inside it
have all eight neighbours alive, so they die of overcrowding all at once.
Uniform random data has no such structure.

That clustered structure is exactly what is under test, so real data is frozen
here. It carries no dates and no account: it is 365 integers between 0 and 4.
"""

# The week starts on Sunday.
REAL_CALENDAR_LEVELS = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 3, 2, 1, 3, 4, 2, 4, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 3, 4, 3, 2, 2, 3, 4, 3, 3, 2, 4, 2, 0, 1, 1, 1, 0, 0, 1, 1, 2, 1, 4, 3, 3, 4, 2, 2,
    3, 1, 2, 3, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 3, 4, 1, 1, 1, 1, 2, 2, 1, 1, 2, 2, 1, 2, 2, 1, 1, 1, 2, 2, 2, 3, 1, 1,
    1, 1, 1, 1, 1,
)
