<?php

// Where the admin console finds the MediFlow services. It owns no patient or visit data itself:
// everything is read and written through these services' APIs (docs/handbook/decisions/ADR-0002).
return [
    // Go auth gateway: login, token refresh, logout.
    'gateway_url' => rtrim(env('MEDIFLOW_GATEWAY_URL', 'http://localhost:8080'), '/'),
    // Django core API: audit log, departments, accounts.
    'api_url' => rtrim(env('MEDIFLOW_API_URL', 'http://localhost:8000'), '/'),
    // Go patient-flow service: today's flow numbers and multi-day reports.
    'flow_url' => rtrim(env('MEDIFLOW_FLOW_URL', 'http://localhost:8090'), '/'),
    'timeout' => (int) env('MEDIFLOW_TIMEOUT', 10),
];
