@extends('layouts.app')
@section('title', 'Queue rules & holidays')
@section('content')
<header class="page-header">
    <div>
        <h1>Queue rules &amp; holidays</h1>
        <p class="subtitle">Targets and thresholds used by the queue, the dashboards and patient notifications.</p>
    </div>
</header>

@if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif

<div class="split">
    <section class="panel">
        <h2>Queue rules</h2>
        <form method="POST" action="{{ route('settings.queue') }}">
            @csrf
            <h3>Longest a patient should wait to be seen (minutes)</h3>
            <div class="field-row">
                @foreach ([1 => 'Immediate', 2 => 'Emergent', 3 => 'Urgent', 4 => 'Less urgent', 5 => 'Non-urgent'] as $esi => $label)
                    <div class="field">
                        <label for="esi{{ $esi }}">ESI {{ $esi }} · {{ $label }}</label>
                        <input id="esi{{ $esi }}" name="esi{{ $esi }}_target_minutes" type="number" min="0" max="1440" required
                               value="{{ old("esi{$esi}_target_minutes", $queue["esi{$esi}_target_minutes"]) }}">
                    </div>
                @endforeach
            </div>
            <h3>Notifications</h3>
            <div class="field-row">
                <div class="field">
                    <label for="long_wait_minutes">“Sorry for the wait” after (minutes)</label>
                    <input id="long_wait_minutes" name="long_wait_minutes" type="number" min="0" max="1440" required
                           value="{{ old('long_wait_minutes', $queue['long_wait_minutes']) }}">
                </div>
                <div class="field">
                    <label for="turn_near_ahead">“Your turn is near” when this many are ahead</label>
                    <input id="turn_near_ahead" name="turn_near_ahead" type="number" min="0" max="20" required
                           value="{{ old('turn_near_ahead', $queue['turn_near_ahead']) }}">
                </div>
            </div>
            <h3>Appointments</h3>
            <div class="field-row">
                <div class="field">
                    <label for="slot_minutes">Slot length (minutes)</label>
                    <select id="slot_minutes" name="slot_minutes">
                        @foreach ([5, 10, 15, 20, 30, 60] as $m)
                            <option value="{{ $m }}" @selected((int) old('slot_minutes', $queue['slot_minutes']) === $m)>{{ $m }}</option>
                        @endforeach
                    </select>
                </div>
                <div class="field">
                    <label for="max_days_ahead">Bookable up to (days ahead)</label>
                    <input id="max_days_ahead" name="max_days_ahead" type="number" min="1" max="365" required
                           value="{{ old('max_days_ahead', $queue['max_days_ahead']) }}">
                </div>
                <div class="field">
                    <label for="min_notice_minutes">Minimum notice (minutes)</label>
                    <input id="min_notice_minutes" name="min_notice_minutes" type="number" min="0" max="1440" required
                           value="{{ old('min_notice_minutes', $queue['min_notice_minutes']) }}">
                </div>
                <div class="field">
                    <label for="max_open_appointments">Open appointments per patient</label>
                    <input id="max_open_appointments" name="max_open_appointments" type="number" min="1" max="20" required
                           value="{{ old('max_open_appointments', $queue['max_open_appointments']) }}">
                </div>
            </div>
            <button type="submit" class="btn">Save queue rules</button>
        </form>
    </section>

    <section class="panel">
        <h2>Holidays</h2>
        <p class="muted small">The clinic takes no appointments on these days. Walk-ins are not affected.</p>
        @if ($holidays === [])
            <p class="muted empty">No upcoming holidays.</p>
        @else
            <table class="table">
                <thead><tr><th>Date</th><th>Holiday</th><th></th></tr></thead>
                <tbody>
                @foreach ($holidays as $holiday)
                    <tr>
                        <td>{{ \Illuminate\Support\Carbon::parse($holiday['date'])->format('D j M Y') }}</td>
                        <td>{{ $holiday['name'] }}</td>
                        <td class="actions">
                            <form method="POST" action="{{ route('settings.holidays.destroy', $holiday['id']) }}">
                                @csrf @method('DELETE')
                                <button type="submit" class="btn btn-small btn-danger">Remove</button>
                            </form>
                        </td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        @endif
        <h3>Add a holiday</h3>
        <form method="POST" action="{{ route('settings.holidays.store') }}">
            @csrf
            <div class="field-row">
                <div class="field"><label for="date">Date</label><input id="date" name="date" type="date" value="{{ old('date') }}" required></div>
                <div class="field"><label for="holiday_name">Name</label><input id="holiday_name" name="name" value="{{ old('name') }}" maxlength="100" required placeholder="Independence Day"></div>
            </div>
            <button type="submit" class="btn">Add holiday</button>
        </form>
    </section>
</div>
@endsection
