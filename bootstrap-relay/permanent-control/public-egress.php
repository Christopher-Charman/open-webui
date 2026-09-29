<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$root = __DIR__ . '/.well-known/powerpc-control-v1';
$kind = $_GET['kind'] ?? 'identity';

if ($kind === 'identity' || $kind === 'status') {
    $path = $root . '/' . $kind . '.json';
} elseif ($kind === 'result') {
    $id = $_GET['id'] ?? '';
    if (!preg_match('/\A[A-Za-z0-9._-]{8,128}\z/', $id)) {
        http_response_code(400);
        echo "{\"error\":\"bad_id\"}\n";
        exit;
    }
    $path = $root . '/results/' . $id . '.json';
} else {
    http_response_code(400);
    echo "{\"error\":\"bad_kind\"}\n";
    exit;
}

if (!is_file($path) || !is_readable($path)) {
    http_response_code(404);
    echo "{\"error\":\"not_found\"}\n";
    exit;
}

$body = file_get_contents($path);
if ($body === false) {
    http_response_code(500);
    echo "{\"error\":\"read_failed\"}\n";
    exit;
}
echo $body;
