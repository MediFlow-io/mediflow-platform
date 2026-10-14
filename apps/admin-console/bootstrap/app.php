<?php

use App\Exceptions\MediflowException;
use App\Exceptions\SessionExpiredException;
use App\Http\Middleware\RequireAdminSession;
use App\Http\Middleware\SecurityHeaders;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->web(append: [SecurityHeaders::class]);
        $middleware->alias(['admin' => RequireAdminSession::class]);
        // Behind Nginx/Docker: trust the proxy's X-Forwarded-* so generated URLs and secure cookies are right.
        $middleware->trustProxies(at: '*');
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        // Session ended or admin rights removed: back to sign-in with an explanation.
        $exceptions->render(function (SessionExpiredException $e, Request $request) {
            $request->session()->invalidate();

            return redirect()->route('login')->withErrors(['session' => $e->getMessage()]);
        });
        // A MediFlow service failed: show a calm error page instead of a stack trace.
        $exceptions->render(function (MediflowException $e, Request $request) {
            return response()->view('errors.service', ['message' => $e->getMessage()], $e->status >= 400 && $e->status < 500 ? $e->status : 502);
        });
    })->create();
