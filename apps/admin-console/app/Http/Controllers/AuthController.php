<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AuthController extends Controller
{
    public function __construct(private readonly MediflowClient $mediflow) {}

    public function show(): View|RedirectResponse
    {
        return $this->mediflow->signedIn() ? redirect()->route('dashboard') : view('auth.login');
    }

    public function login(Request $request): RedirectResponse
    {
        $credentials = $request->validate([
            'username' => ['required', 'string', 'max:150'],
            'password' => ['required', 'string', 'max:256'],
        ]);
        try {
            // Brute-force protection is enforced by the core API (per IP and username).
            $result = $this->mediflow->login($credentials['username'], $credentials['password']);
        } catch (MediflowException $e) {
            return back()->withInput($request->only('username'))->withErrors(['username' => $e->getMessage()]);
        }
        if (! empty($result['mfa_required'])) {
            return redirect()->route('login.code');
        }
        $request->session()->regenerate(); // new session id after sign-in (session fixation)

        return redirect()->intended(route('dashboard'));
    }

    public function showCode(): View|RedirectResponse
    {
        return $this->mediflow->awaitingMfa() ? view('auth.code') : redirect()->route('login');
    }

    public function verifyCode(Request $request): RedirectResponse
    {
        $data = $request->validate(['code' => ['required', 'digits:6']], ['code.digits' => 'Enter the 6-digit code.']);
        try {
            $this->mediflow->verifyMfa($data['code']);
        } catch (MediflowException $e) {
            $route = $this->mediflow->awaitingMfa() ? 'login.code' : 'login';

            return redirect()->route($route)->withErrors(['code' => $e->getMessage()]);
        }
        $request->session()->regenerate();

        return redirect()->intended(route('dashboard'));
    }

    public function logout(Request $request): RedirectResponse
    {
        $this->mediflow->logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect()->route('login')->with('status', 'You have signed out.');
    }
}
