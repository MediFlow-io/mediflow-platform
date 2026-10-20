<?php

namespace App\Exceptions;

use RuntimeException;

/** An error answer from a MediFlow service (status 0 = the service couldn't be reached). */
class MediflowException extends RuntimeException
{
    /** @param array<string, list<string>> $errors field => messages, as Django REST Framework returns them */
    public function __construct(string $message, public readonly int $status = 0, public readonly array $errors = [])
    {
        parent::__construct($message);
    }

    public static function fromResponse(int $status, mixed $body): self
    {
        if (is_array($body) && isset($body['detail']) && is_string($body['detail'])) {
            return new self($body['detail'], $status);
        }
        $errors = [];
        if (is_array($body)) {
            foreach ($body as $field => $messages) {
                $errors[(string) $field] = self::flatten($messages);
            }
        }
        $parts = [];
        foreach ($errors as $field => $messages) {
            $parts[] = ($field === 'non_field_errors' ? '' : "$field: ").implode(' ', $messages);
        }

        return new self($parts ? implode(' ', $parts) : "The MediFlow service answered with an error ($status).", $status, $errors);
    }

    /** Messages can be nested (e.g. one list per row of a submitted week): collect them all as strings. */
    private static function flatten(mixed $messages): array
    {
        if (! is_array($messages)) {
            return [(string) $messages];
        }
        $out = [];
        array_walk_recursive($messages, function ($message) use (&$out) {
            $out[] = (string) $message;
        });

        return $out;
    }
}
