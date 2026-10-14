<?php

namespace App\Http\Middleware;

use App\Services\MediflowClient;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Only signed-in administrators get past this point. The MediFlow APIs check the admin role again
 * on every call, so a role change or deactivation ends the console session (see MediflowClient).
 */
class RequireAdminSession
{
    public function __construct(private readonly MediflowClient $mediflow) {}

    public function handle(Request $request, Closure $next): Response
    {
        if (! $this->mediflow->signedIn()) {
            return redirect()->guest(route('login'));
        }
        view()->share('adminUser', $this->mediflow->user());

        return $next($request);
    }
}
