<?php

namespace App\Services;

use App\Exceptions\MediflowException;
use App\Exceptions\SessionExpiredException;
use Illuminate\Contracts\Session\Session;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

/**
 * HTTP client for the MediFlow services, acting as the signed-in administrator.
 *
 * Tokens live only in the server-side session, never in the browser. An expired access token is
 * refreshed once (refresh tokens are single-use and rotate); if that fails, the session has ended.
 */
class MediflowClient
{
    public const SESSION_KEY = 'mediflow';

    public function __construct(private readonly Session $session) {}

    /** Sign in through the gateway. Only administrators may use the admin console. */
    public function login(string $username, string $password): array
    {
        $response = $this->send('post', config('mediflow.gateway_url').'/api/auth/login',
            ['unique_id' => $username, 'password' => $password], null);
        if (! $response->successful()) {
            throw MediflowException::fromResponse($response->status(), $response->json());
        }
        $data = $response->json();
        if (($data['role'] ?? null) !== 'admin') {
            $this->revoke($data['refresh'] ?? null);
            throw new MediflowException('The admin console is for administrators only.', 403);
        }
        $this->session->put(self::SESSION_KEY, [
            'access' => $data['access'],
            'refresh' => $data['refresh'],
            'user' => ['id' => $data['id'], 'username' => $data['username'], 'name' => $data['name'] ?? $data['username']],
        ]);

        return $data;
    }

    public function logout(): void
    {
        $this->revoke($this->session->get(self::SESSION_KEY.'.refresh'));
        $this->session->forget(self::SESSION_KEY);
    }

    public function signedIn(): bool
    {
        return $this->session->has(self::SESSION_KEY.'.access');
    }

    public function user(): ?array
    {
        return $this->session->get(self::SESSION_KEY.'.user');
    }

    // ------------------------------------------------------------------ API calls

    public function flowToday(): array
    {
        return $this->json('get', 'flow', '/api/dashboard');
    }

    public function flowReport(?string $from, ?string $to): array
    {
        return $this->json('get', 'flow', '/api/reports/flow', array_filter(['from' => $from, 'to' => $to]));
    }

    public function auditLogs(array $filters, int $page = 1, int $pageSize = 50): array
    {
        return $this->json('get', 'api', '/api/audit-logs', array_filter($filters) + ['page' => $page, 'page_size' => $pageSize]);
    }

    public function departments(): array
    {
        return $this->json('get', 'api', '/api/departments');
    }

    public function createDepartment(array $data): array
    {
        return $this->json('post', 'api', '/api/departments', $data);
    }

    public function updateDepartment(int $id, array $data): array
    {
        return $this->json('patch', 'api', "/api/departments/$id", $data);
    }

    // ------------------------------------------------------------------ plumbing

    private function json(string $method, string $service, string $path, array $data = []): array
    {
        $url = config("mediflow.{$service}_url").$path;
        $response = $this->send($method, $url, $data, $this->session->get(self::SESSION_KEY.'.access'));
        if ($response->status() === 401 && $this->refresh()) {
            $response = $this->send($method, $url, $data, $this->session->get(self::SESSION_KEY.'.access'));
        }
        if ($response->status() === 401) {
            $this->session->forget(self::SESSION_KEY);
            throw new SessionExpiredException('Your session has ended. Please sign in again.', 401);
        }
        if ($response->status() === 403) {
            // The account is no longer an administrator: end the console session.
            $this->logout();
            throw new SessionExpiredException('Your account no longer has administrator access.', 403);
        }
        if (! $response->successful()) {
            throw MediflowException::fromResponse($response->status(), $response->json());
        }

        return $response->json() ?? [];
    }

    private function refresh(): bool
    {
        $refresh = $this->session->get(self::SESSION_KEY.'.refresh');
        if (! $refresh) {
            return false;
        }
        $response = $this->send('post', config('mediflow.gateway_url').'/api/auth/token/refresh', ['refresh' => $refresh], null);
        if (! $response->successful()) {
            return false;
        }
        $this->session->put(self::SESSION_KEY.'.access', $response->json('access'));
        $this->session->put(self::SESSION_KEY.'.refresh', $response->json('refresh'));

        return true;
    }

    private function revoke(?string $refresh): void
    {
        if (! $refresh) {
            return;
        }
        try {
            $this->send('post', config('mediflow.gateway_url').'/api/auth/logout', ['refresh' => $refresh], null);
        } catch (MediflowException) {
            // Signing out locally is what matters; the token expires on its own.
        }
    }

    private function send(string $method, string $url, array $data, ?string $token): Response
    {
        $request = Http::acceptJson()->timeout(config('mediflow.timeout'));
        if ($token) {
            $request = $request->withToken($token);
        }
        try {
            return $method === 'get' ? $request->get($url, $data) : $request->{$method}($url, $data);
        } catch (ConnectionException) {
            throw new MediflowException('A MediFlow service could not be reached. Please try again shortly.', 0);
        }
    }
}
