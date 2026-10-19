<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title', 'Admin') · MediFlow admin</title>
    <link rel="stylesheet" href="{{ asset('css/admin.css') }}">
</head>
<body>
@isset($adminUser)
<div class="app">
    <aside class="sidebar">
        <div class="brand"><span class="brand-mark"></span><span class="brand-name">MediFlow</span><span class="brand-tag">admin</span></div>
        <nav aria-label="Main">
            @foreach ([['dashboard', 'Overview'], ['reports', 'Flow reports'], ['audit', 'Audit log'], ['departments', 'Departments'],
                       ['settings', 'Queue rules & holidays'], ['settings.hours', 'Opening hours'], ['settings.rota', 'Staff rota']] as [$route, $label])
                @php($here = $route === 'settings' ? request()->routeIs('settings') || request()->routeIs('settings.queue', 'settings.holidays.*') : request()->routeIs($route.'*'))
                <a href="{{ route($route) }}" class="nav-item {{ $here ? 'active' : '' }}" @if ($here) aria-current="page" @endif>{{ $label }}</a>
            @endforeach
        </nav>
        <div class="sidebar-foot">
            <div class="small"><strong>{{ $adminUser['name'] }}</strong></div>
            <div class="small muted">administrator</div>
            <form method="POST" action="{{ route('logout') }}">@csrf<button type="submit" class="btn-link">Sign out</button></form>
        </div>
    </aside>
    <main class="content">
        @if (session('status'))<div class="success-box" role="status">{{ session('status') }}</div>@endif
        @yield('content')
    </main>
</div>
@else
<div class="shell">@yield('content')</div>
@endisset
</body>
</html>
