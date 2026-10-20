@if (count($rows) === 0)
    <p class="muted empty">No visits in this period.</p>
@else
    <table class="table">
        <thead><tr><th>{{ $label }}</th><th class="num">Check-ins</th><th class="num">Completed</th><th class="num">Cancelled</th><th class="num">Avg wait</th><th class="num">Avg consultation</th></tr></thead>
        <tbody>
        @foreach ($rows as $row)
            <tr>
                <td>{{ $key === 'esi' ? 'ESI '.$row['esi'] : $row[$key] }}</td>
                <td class="num">{{ $row['checkIns'] }}</td>
                <td class="num">{{ $row['completed'] }}</td>
                <td class="num">{{ $row['cancelled'] }}</td>
                <td class="num">{{ isset($row['averageWaitMinutes']) ? $row['averageWaitMinutes'].' min' : '—' }}</td>
                <td class="num">{{ isset($row['averageConsultationMinutes']) ? $row['averageConsultationMinutes'].' min' : '—' }}</td>
            </tr>
        @endforeach
        </tbody>
    </table>
@endif
