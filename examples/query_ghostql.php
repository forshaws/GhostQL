<?php
/**
 * examples/query_ghostql.php
 * GhostQL PHP Example Client v1.0.0
 *
 * Demonstrates all GhostQL query types against a running GhostQL server:
 *   - Plain SELECT (no hashing)
 *   - SELECT WITH PQR (hashed tokens)
 *   - SELECT WITH PQR FPD (false positive defence)
 *   - Multi-condition AND query
 *   - LIKE similarity search
 *   - JOIN two result sets
 *
 * Prerequisites:
 *   1. GhostQL server running: python -m ghostql.server
 *   2. ghostql.conf configured with valid DMM credentials
 *
 * Usage:
 *   php examples/query_ghostql.php
 *
 * Configuration (edit below or set environment variables):
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

stream_set_blocking($socket, false);
stream_set_timeout($socket, 10);

echo "\n";
echo "╔══════════════════════════════════════════════════════╗\n";
echo "║       GhostQL PHP Example Client v1.0.0             ║\n";
echo "╚══════════════════════════════════════════════════════╝\n\n";


// ── Helpers ───────────────────────────────────────────────────────────────────

function readUntilPrompt(mixed $socket, int $timeout = 10): string {
    $buffer = '';
    $end    = time() + $timeout;
    while (time() < $end) {
        $line = fgets($socket);
        if ($line !== false) {
            $buffer .= $line;
            if (trim($line) === '>') break;
        } else {
            usleep(50000);
        }
    }
    return $buffer;
}

function sendQuery(mixed $socket, string $query, int $timeout = 30): array {
    echo "┌─ Query ────────────────────────────────────────────────\n";
    echo "│  $query\n";
    echo "└────────────────────────────────────────────────────────\n";

    fwrite($socket, $query . "\n");
    fflush($socket);

    $raw = readUntilPrompt($socket, $timeout);

    // Extract JSON block
    $start = -1;
    for ($i = 0; $i < strlen($raw); $i++) {
        if ($raw[$i] === '[' || $raw[$i] === '{') { $start = $i; break; }
    }

    $data = null;
    if ($start !== -1) {
        for ($end = strlen($raw); $end > $start; $end--) {
            $decoded = json_decode(substr($raw, $start, $end - $start), true);
            if ($decoded !== null) { $data = $decoded; break; }
        }
    }

    if ($data === null) {
        echo "  RAW: " . trim($raw) . "\n\n";
        return [];
    }

    // Status / no-match
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

    // Results
    $count = count($data);
    echo "  ✓  $count document(s) matched:\n";
    foreach ($data as $i => $row) {
        $doc = $row['document'] ?? json_encode($row);
        echo "  [" . ($i + 1) . "] $doc\n";
        // Show extra fields (overlap_pct for LIKE, join for JOIN)
        foreach (['overlap_pct', 'token_hits', 'join', 'on'] as $f) {
            if (isset($row[$f])) echo "       $f={$row[$f]}\n";
        }
    }
    echo "\n";
    return $data;
}

// ── Authenticate ──────────────────────────────────────────────────────────────

$banner = readUntilPrompt($socket, 5);
echo trim($banner) . "\n\n";

fwrite($socket, "$user\n"); fflush($socket); usleep(200000);
fwrite($socket, "$pass\n"); fflush($socket);
$auth = readUntilPrompt($socket, 5);
echo trim($auth) . "\n\n";

// ── Queries ───────────────────────────────────────────────────────────────────

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 1 — Plain SELECT (no hashing)\n";
echo "  Expected: NO_MATCHES if dataset was ingested with PQR\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM records WHERE name='Mills'",
    10
);

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 2 — SELECT WITH PQR (hashed tokens, no FPD)\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM records WHERE name='Mills' WITH PQR",
    20
);

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 3 — SELECT WITH PQR FPD (full false-positive defence)\n";
echo "  This is the correct mode for PQR+FPD-ingested datasets\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM records WHERE name='Mills' WITH PQR FPD",
    40
);

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 4 — Multi-condition AND query WITH PQR FPD\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD",
    60
);

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 5 — LIKE similarity search WITH PQR FPD\n";
echo "  Tokenises the free text, scores documents by overlap\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM records WHERE notes LIKE 'Mills pharmacy medication review' WITH PQR FPD",
    60
);

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "  Test 6 — JOIN two result sets ON shared field\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
sendQuery($socket,
    "SELECT document FROM patients JOIN prescriptions ON nhs_number WHERE name='Mills' WITH PQR FPD",
    60
);

// ── Close ─────────────────────────────────────────────────────────────────────

fwrite($socket, "quit\n");
fclose($socket);
echo "Done.\n\n";
?>
