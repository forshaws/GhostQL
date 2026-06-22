<?php
/**
 * examples/query_ghostql_demo.php
 * GhostQL Demo Client v1.0.0 — Local Dataset
 *
 * Demonstrates all GhostQL query types against the bundled demo dataset.
 * No DMM credentials required — works out of the box with:
 *
 *   [connector]
 *   type = local
 *
 * Usage:
 *   php examples/query_ghostql_demo.php
 *
 * Credentials via environment variables or defaults below:
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
      . "    Is the server running?  python -m ghostql.server\n"
      . "    Is ghostql.conf set to connector.type = local?\n");
}
stream_set_blocking($socket, true);
stream_set_timeout($socket, 10);

echo "\n";
echo "╔══════════════════════════════════════════════════════╗\n";
echo "║  GhostQL Demo Client v1.0.0                          ║\n";
echo "║  Local dataset · 500 synthetic records               ║\n";
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
    echo "┌─ $query\n";
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
        $end     = strrpos($raw, $endChar);
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
        $msg = $data[0]['message'] ?? '';
        echo "  ⚠  {$data[0]['status']} — $msg\n";
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
    foreach (array_slice($data, 0, 3) as $i => $row) {
		$doc = $row['document'] ?? json_encode($row);
		$pct = isset($row['overlap_pct']) ? "  ({$row['overlap_pct']}%)" : '';
		echo "  [" . ($i + 1) . "] $doc$pct\n";
	}
    if ($count > 3) echo "  … and " . ($count - 3) . " more\n";
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
    echo "  export GHOSTQL_PASS=your_password_from_ghostql_conf\n";
    fclose($socket);
    exit(1);
}

// ── Queries ───────────────────────────────────────────────────────────────────

sendQuery($socket,
    "Plain SELECT — no hashing (expected: NO_MATCHES)",
    "SELECT document FROM patients WHERE name='Mills'"
);

sendQuery($socket,
    "SELECT WITH PQR FPD — find all patients named Mills",
    "SELECT document FROM patients WHERE name='Mills' WITH PQR FPD"
);

sendQuery($socket,
    "SELECT WITH PQR FPD — find all clinical records with diabetes",
    "SELECT document FROM clinical WHERE dlbl='Diabetes' WITH PQR FPD"
);

sendQuery($socket,
    "Multi-condition AND — patients in Scarborough at Parkway Medical",
    "SELECT document FROM patients WHERE town='Scarborough' AND gp='Parkway' WITH PQR FPD"
);

sendQuery($socket,
    "Multi-condition AND — clinical records with hypertension on Metformin",
    "SELECT document FROM clinical WHERE dlbl='Hypertension' AND mlbl='Metformin' WITH PQR FPD"
);

sendQuery($socket,
    "LIKE — similarity search across diagnosis labels",
    "SELECT document FROM clinical WHERE dlbl LIKE 'Alzheimer Crohn\'s Psoriasis' WITH PQR FPD",
    60
);

sendQuery($socket,
    "LIKE — find patients on related medications",
    "SELECT document FROM clinical WHERE mlbl LIKE 'Metformin Warfarin Sertraline' WITH PQR FPD",
    60
);

sendQuery($socket,
    "JOIN — find clinical records for patients named Mills via NHS number",
    "SELECT document FROM patients JOIN clinical ON nhs WHERE name='Mills' WITH PQR FPD",
    60
);

// ── Close ─────────────────────────────────────────────────────────────────────
sendLine($socket, 'quit');
fclose($socket);
echo "Done.\n\n";
?>
