<?php
/**
 * examples/query_ghostql.php
 * GhostQL PHP Example Client v1.1.0
 *
 * Demonstrates all GhostQL query types against a running GhostQL server.
 *
 * Prerequisites:
 *   1. GhostQL server running: python -m ghostql.server
 *   2. ghostql.conf configured with valid DMM credentials
 *
 * Usage:
 *   php examples/query_ghostql.php
 *
 * Credentials (set env vars or edit defaults below):
 *   GHOSTQL_HOST, GHOSTQL_PORT, GHOSTQL_USER, GHOSTQL_PASS
 */

$host = getenv('GHOSTQL_HOST') ?: '127.0.0.1';
$port = (int)(getenv('GHOSTQL_PORT') ?: 5051);
$user = getenv('GHOSTQL_USER') ?: 'admin';
$pass = getenv('GHOSTQL_PASS') ?: 'changeme';

// ── Connection ────────────────────────────────────────────────────────────────

$socket = @fsockopen($host, $port, $errno, $errstr, 5);
if (!$socket) {
    die("  ✗ Could not connect to GhostQL at $host:$port\n"
      . "    Error: $errstr ($errno)\n"
      . "    Is the server running?  python -m ghostql.server\n");
}
stream_set_blocking($socket, true);
stream_set_timeout($socket, 10);

echo "\n";
echo "╔══════════════════════════════════════════════════════╗\n";
echo "║        GhostQL PHP Example Client v1.1.0             ║\n";
echo "╚══════════════════════════════════════════════════════╝\n\n";


// ── Helpers ───────────────────────────────────────────────────────────────────

function readUntilMarker(mixed $socket, string $marker, int $timeout = 10): string {
    $buffer = '';
    $end    = time() + $timeout;
    stream_set_timeout($socket, 1);
    while (time() < $end) {
        $line = fgets($socket, 4096);
        if ($line !== false) {
            $buffer .= $line;
            if (strpos($buffer, $marker) !== false) break;
        }
        $info = stream_get_meta_data($socket);
        if ($info['timed_out']) continue;
        if (feof($socket)) break;
    }
    return $buffer;
}

function sendLine(mixed $socket, string $text): void {
    fwrite($socket, $text . "\n");
    fflush($socket);
}

function sendQuery(mixed $socket, string $label, string $query, int $timeout = 30): array {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    echo "  $label\n";
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    echo "┌─ Query ────────────────────────────────────────────────\n";
    echo "│  $query\n";
    echo "└────────────────────────────────────────────────────────\n";

    sendLine($socket, $query);
    $raw = readUntilMarker($socket, '>', $timeout);

    $start = -1;
    for ($i = 0; $i < strlen($raw); $i++) {
        if ($raw[$i] === '[' || $raw[$i] === '{') { $start = $i; break; }
    }

    $data = null;
    if ($start !== -1) {
        $endChar = ($raw[$start] === '[') ? ']' : '}';
        $end = strrpos($raw, $endChar);
        if ($end !== false) {
            $decoded = json_decode(substr($raw, $start, $end - $start + 1), true);
            if ($decoded !== null) $data = $decoded;
        }
    }

    if ($data === null) {
        echo "  RAW: " . trim($raw) . "\n\n";
        return [];
    }

    if (isset($data['status']) || isset($data['document'])) {
        $data = [$data];
    }

    if (isset($data[0]['status'])) {
        $status = $data[0]['status'];
        $msg    = $data[0]['message'] ?? '';
        echo "  ⚠  $status — $msg\n";
        if (!empty($data[0]['search_summary'])) {
            foreach ($data[0]['search_summary'] as $token => $count) {
                echo "       '$token' → $count hit(s)\n";
            }
        }
        echo "\n";
        return [];
    }

    $count = count($data);
    echo "  ✓  $count document(s) matched:\n";
    foreach (array_slice($data, 0, 5) as $i => $row) {
        $doc = $row['document'] ?? json_encode($row);
        $pct = isset($row['overlap_pct']) ? "  ({$row['overlap_pct']}%)" : '';
        echo "  [" . ($i + 1) . "] $doc$pct\n";
    }
    if ($count > 5) echo "  … and " . ($count - 5) . " more\n";
    echo "\n";
    return $data;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

$banner = readUntilMarker($socket, 'Username:');
echo $banner . "\n\n";

sendLine($socket, $user);
readUntilMarker($socket, 'Password:');
echo "Password:\n";

sendLine($socket, $pass);
$auth = readUntilMarker($socket, '>');
echo trim($auth) . "\n\n";

if (strpos($auth, 'ERROR') !== false) {
    echo "✗ Authentication failed.\n";
    echo "  Set credentials via environment variables:\n";
    echo "    export GHOSTQL_USER=admin\n";
    echo "    export GHOSTQL_PASS=your_password_from_ghostql_conf\n";
    fclose($socket);
    exit(1);
}

// ── Queries ───────────────────────────────────────────────────────────────────

sendQuery($socket,
    "Test 1 — Plain SELECT, no hashing (expected: NO_MATCHES on PQR-ingested data)",
    "SELECT document FROM records WHERE name='Mills'"
);

sendQuery($socket,
    "Test 2 — SELECT WITH PQR — hashed tokens, no FPD",
    "SELECT document FROM records WHERE name='Mills' WITH PQR",
    20
);

sendQuery($socket,
    "Test 3 — SELECT WITH PQR FPD — correct mode for PQR+FPD-ingested data",
    "SELECT document FROM records WHERE name='Mills' WITH PQR FPD",
    40
);

sendQuery($socket,
    "Test 4 — AND — multi-condition intersection, pinpoint a single record",
    "SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD",
    60
);

sendQuery($socket,
    "Test 5 — LIKE — similarity search, ranked by token overlap",
    "SELECT document FROM records WHERE dlbl LIKE 'Retinal detachment' WITH PQR FPD",
    60
);

sendQuery($socket,
    "Test 6 — JOIN — cross-dataset join via shared field token",
    "SELECT document FROM patients JOIN clinical ON nhs WHERE name='Mills' WITH PQR FPD",
    60
);

sendQuery($socket,
    "Test 7 — OR — union of two name searches",
    "SELECT document FROM records WHERE name='Mills' OR name='Chen' WITH PQR FPD",
    60
);

sendQuery($socket,
    "Test 8 — OR — union across different fields",
    "SELECT document FROM records WHERE dlbl='Diabetes' OR mlbl='Metformin' WITH PQR FPD",
    60
);

sendQuery($socket,
    "Test 9 — Mixed AND/OR — AND binds tighter, (Mills AND Retinal) OR Diabetes",
    "SELECT document FROM records WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes' WITH PQR FPD",
    60
);

// ── Close ─────────────────────────────────────────────────────────────────────
sendLine($socket, 'quit');
fclose($socket);
echo "Done.\n\n";
?>
