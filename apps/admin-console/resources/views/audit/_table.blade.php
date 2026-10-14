@if (count($entries) === 0)
    <p class="muted empty">No audit entries match.</p>
@else
    <table class="table">
        <thead><tr><th>When</th><th>Who</th><th>Action</th>@unless ($compact ?? false)<th>Record</th><th>Details</th>@endunless</tr></thead>
        <tbody>
        @foreach ($entries as $entry)
            <tr>
                <td class="nowrap">{{ \Illuminate\Support\Carbon::parse($entry['created_at'])->format('j M H:i:s') }}</td>
                <td>{{ $entry['actor'] ?? 'anonymous' }}@if ($entry['actor_role'] ?? null) <span class="muted small">({{ $entry['actor_role'] }})</span>@endif</td>
                <td><code class="{{ str_contains($entry['action'], 'failed') || str_contains($entry['action'], 'deleted') ? 'text-alert' : '' }}">{{ $entry['action'] }}</code></td>
                @unless ($compact ?? false)
                    <td class="nowrap">{{ $entry['entity_type'] }}@if ($entry['entity_id'] !== '') #{{ $entry['entity_id'] }}@endif</td>
                    <td class="details">@if (! empty($entry['details']))<code>{{ json_encode($entry['details'], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) }}</code>@endif</td>
                @endunless
            </tr>
        @endforeach
        </tbody>
    </table>
@endif
