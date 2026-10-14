# Laravel admin console. Build context: apps/admin-console.
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction --no-progress
COPY . .
RUN composer dump-autoload --no-dev --optimize --classmap-authoritative

FROM php:8.3-apache
# Serve only public/; let Laravel's .htaccess route requests.
RUN a2enmod rewrite headers \
 && sed -ri 's!/var/www/html!/var/www/html/public!g' /etc/apache2/sites-available/000-default.conf \
 && sed -ri 's!AllowOverride None!AllowOverride All!g' /etc/apache2/apache2.conf \
 && echo 'ServerTokens Prod\nServerSignature Off' > /etc/apache2/conf-enabled/zz-hardening.conf
WORKDIR /var/www/html
COPY --from=vendor /app ./
RUN mkdir -p storage/framework/sessions storage/framework/views storage/framework/cache storage/logs bootstrap/cache \
 && chown -R www-data:www-data storage bootstrap/cache
ENV APP_ENV=production LOG_CHANNEL=stderr SESSION_DRIVER=file CACHE_STORE=file QUEUE_CONNECTION=sync
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD curl -fsS http://127.0.0.1/up || exit 1
