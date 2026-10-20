@php($max = max([1, ...array_map(fn ($d) => $d["checkIns"], $days)]))
@if (array_sum(array_map(fn ($d) => $d['checkIns'], $days)) === 0)
    <p class="muted empty">No check-ins in this period.</p>
@else
    <table class="table bars" aria-label="Check-ins per day">
        <thead><tr><th>Day</th><th>Check-ins</th><th class="num">Count</th></tr></thead>
        <tbody>
        @foreach ($days as $day)
            <tr>
                <td class="nowrap">{{ \Illuminate\Support\Carbon::parse($day['date'])->format('D j M') }}</td>
                <td class="bar-cell"><meter class="bar" min="0" max="{{ $max }}" value="{{ $day['checkIns'] }}"></meter></td>
                <td class="num">{{ $day['checkIns'] }}</td>
            </tr>
        @endforeach
        </tbody>
    </table>
@endif
