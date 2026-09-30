<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$root = __DIR__ . '/.well-known/powerpc-control-v1';

function emit_bad(string $reason, int $status = 400): never {
    http_response_code($status);
    echo json_encode(['error' => $reason], JSON_UNESCAPED_SLASHES) . "\n";
    exit;
}

function valid_task_id(string $id): bool {
    return preg_match('/\A[A-Za-z0-9._-]{8,128}\z/', $id) === 1;
}

$path = null;
$pathInfo = $_SERVER['PATH_INFO'] ?? '';

if ($pathInfo !== '') {
    $parts = array_values(array_filter(explode('/', trim($pathInfo, '/')), 'strlen'));

    if (count($parts) === 1 && ($parts[0] === 'identity.json' || $parts[0] === 'status.json')) {
        $kind = substr($parts[0], 0, -5);
        $path = $root . '/' . $kind . '.json';
    } elseif (count($parts) === 2 && $parts[0] === 'result') {
        $leaf = $parts[1];
        if (!str_ends_with($leaf, '.json')) {
            emit_bad('bad_result_path');
        }
        $id = substr($leaf, 0, -5);
        if (!valid_task_id($id)) {
            emit_bad('bad_id');
        }
        $path = $root . '/results/' . $id . '.json';
    } else {
        emit_bad('bad_path');
    }
} else {
    $kind = $_GET['kind'] ?? 'identity';

    if ($kind === 'identity' || $kind === 'status') {
        $path = $root . '/' . $kind . '.json';
    } elseif ($kind === 'result') {
        $id = $_GET['id'] ?? '';
        if (!valid_task_id($id)) {
            emit_bad('bad_id');
        }
        $path = $root . '/results/' . $id . '.json';
    } else {
        emit_bad('bad_kind');
    }
}

if ($path === null || !is_file($path) || !is_readable($path)) {
    emit_bad('not_found', 404);
}

$body = file_get_contents($path);
if ($body === false) {
    emit_bad('read_failed', 500);
}

echo $body;
