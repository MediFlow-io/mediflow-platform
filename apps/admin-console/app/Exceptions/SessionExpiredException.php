<?php

namespace App\Exceptions;

/** The admin's MediFlow session can't be used any more (expired, revoked, or no longer an admin). */
class SessionExpiredException extends MediflowException
{
}
