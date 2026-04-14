# MSPDI XML Schema Reference

## Namespace

```
http://schemas.microsoft.com/project
```

All elements use this default namespace. Register before parsing:
```python
ET.register_namespace('', 'http://schemas.microsoft.com/project')
```

## Top-Level Structure

```xml
<Project xmlns="http://schemas.microsoft.com/project">
  <!-- Project properties -->
  <SaveVersion>14</SaveVersion>
  <Name>...</Name>
  <Title>...</Title>
  <StartDate>...</StartDate>
  <FinishDate>...</FinishDate>
  <CalendarUID>1</CalendarUID>
  <MinutesPerDay>480</MinutesPerDay>
  <MinutesPerWeek>2400</MinutesPerWeek>
  <DaysPerMonth>20</DaysPerMonth>

  <Calendars>...</Calendars>
  <Tasks>...</Tasks>
  <Resources>...</Resources>
  <Assignments>...</Assignments>
</Project>
```

## Task Element

```xml
<Task>
  <UID>1</UID>                          <!-- Unique ID (integer, immutable) -->
  <ID>1</ID>                            <!-- Display order ID -->
  <Name>Task Name</Name>
  <WBS>1.1.2</WBS>                      <!-- Work Breakdown Structure code -->
  <OutlineLevel>2</OutlineLevel>        <!-- Hierarchy depth (0=project, 1=phase...) -->
  <Start>2026-04-15T08:00:00</Start>    <!-- Planned start (ISO 8601) -->
  <Finish>2026-05-30T17:00:00</Finish>  <!-- Planned finish -->
  <Duration>PT360H0M0S</Duration>       <!-- Planned duration (ISO 8601 period) -->
  <PercentComplete>50</PercentComplete> <!-- 0-100 -->
  <Summary>0</Summary>                  <!-- 1 if has children, 0 if leaf -->
  <Milestone>0</Milestone>              <!-- 1 if milestone (0 duration) -->
  <Critical>1</Critical>                <!-- 1 if on critical path -->
  <ActualStart>2026-04-15T08:00:00</ActualStart>
  <ActualFinish/>                       <!-- Empty if not complete -->
  <ActualDuration>PT180H0M0S</ActualDuration>
  <RemainingDuration>PT180H0M0S</RemainingDuration>
  <ConstraintType>0</ConstraintType>    <!-- 0=ASAP, 2=FNLT, etc. -->
  <CalendarUID>1</CalendarUID>
  <Notes>Free text notes</Notes>
  <PredecessorLink>                     <!-- Task dependencies -->
    <PredecessorUID>3</PredecessorUID>
    <Type>1</Type>                      <!-- 0=FF, 1=FS, 2=SF, 3=SS -->
    <LinkLag>0</LinkLag>
  </PredecessorLink>
</Task>
```

### Key Task Fields

| Field | Type | Description |
|-------|------|-------------|
| UID | int | Unique identifier (never reuse after deletion) |
| ID | int | Display order (may change on reorder) |
| Name | string | Task name |
| WBS | string | Dot-separated hierarchy code |
| OutlineLevel | int | Depth in hierarchy (0=project root) |
| Start | datetime | ISO 8601 planned start |
| Finish | datetime | ISO 8601 planned finish |
| Duration | PT string | ISO 8601 duration (`PT###H##M##S`) |
| PercentComplete | int | 0-100 completion percentage |
| Summary | 0/1 | 1 if parent of child tasks |
| Milestone | 0/1 | 1 if zero-duration marker |
| Critical | 0/1 | 1 if on the critical path |
| Notes | string | Free-text notes |

## Resource Element

```xml
<Resource>
  <UID>1</UID>
  <ID>1</ID>
  <Name>Engineer A</Name>
  <Type>1</Type>          <!-- 0=Material, 1=Work, 2=Cost -->
  <MaxUnits>1.00</MaxUnits>
  <StandardRate>0</StandardRate>
  <CalendarUID>2</CalendarUID>
</Resource>
```

## Assignment Element

```xml
<Assignment>
  <UID>1</UID>
  <TaskUID>5</TaskUID>        <!-- References Task.UID -->
  <ResourceUID>1</ResourceUID> <!-- References Resource.UID; -65535 = unassigned -->
  <Units>1.00</Units>
  <Start>2026-04-15T08:00:00</Start>
  <Finish>2026-05-30T17:00:00</Finish>
  <Work>PT360H0M0S</Work>
</Assignment>
```

## Calendar Element

```xml
<Calendar>
  <UID>1</UID>
  <Name>Standard</Name>
  <IsBaseCalendar>1</IsBaseCalendar>
  <WeekDays>
    <WeekDay>
      <DayType>1</DayType>       <!-- 1=Sunday ... 7=Saturday -->
      <DayWorking>0</DayWorking>  <!-- 0=non-working, 1=working -->
      <WorkingTimes>
        <WorkingTime>
          <FromTime>08:00:00</FromTime>
          <ToTime>12:00:00</ToTime>
        </WorkingTime>
        <WorkingTime>
          <FromTime>13:00:00</FromTime>
          <ToTime>17:00:00</ToTime>
        </WorkingTime>
      </WorkingTimes>
    </WeekDay>
  </WeekDays>
</Calendar>
```

### DayType Values

| Value | Day |
|-------|-----|
| 1 | Sunday |
| 2 | Monday |
| 3 | Tuesday |
| 4 | Wednesday |
| 5 | Thursday |
| 6 | Friday |
| 7 | Saturday |

## Duration Format

Microsoft Project uses ISO 8601 duration: `PT{hours}H{minutes}M{seconds}S`

| Duration | Hours | Working Days (8h) |
|----------|-------|-------------------|
| PT0H0M0S | 0 | 0 (milestone) |
| PT8H0M0S | 8 | 1 |
| PT40H0M0S | 40 | 5 (1 week) |
| PT160H0M0S | 160 | 20 (1 month) |
| PT760H0M0S | 760 | 95 |

## Dependency Types

| Type Value | Name | Meaning |
|------------|------|---------|
| 0 | FF | Finish-to-Finish |
| 1 | FS | Finish-to-Start (default) |
| 2 | SF | Start-to-Finish |
| 3 | SS | Start-to-Start |

## Constraint Types

| Value | Name |
|-------|------|
| 0 | As Soon As Possible |
| 1 | As Late As Possible |
| 2 | Finish No Later Than |
| 3 | Finish No Earlier Than |
| 4 | Must Start On |
| 5 | Must Finish On |
| 6 | Start No Later Than |
| 7 | Start No Earlier Than |
