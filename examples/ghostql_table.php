<?php
/**
 * examples/ghostql_table.php
 * GhostQL — MySQL-style table result demo
 *
 * Runs a single query and prints all matching document references
 * as a formatted table — just like a MySQL result set.
 *
 * In a real application, each filereference would be used to fetch
 * the actual document content — a JSON record, a PDF, an image,
 * a medical record, whatever was ingested. GhostQL finds the
 * references; your app fetches the content.
 *
 * Usage:
 *   php examples/ghostql_table.php
 */

$host = getenv('GHOSTQL_HOST') ?: '127.0.0.1';
$port = (int)(getenv('GHOSTQL_PORT') ?: 5051);
$user = getenv('GHOSTQL_USER') ?: 'admin';
$pass = getenv('GHOSTQL_PASS') ?: 'changeme';


$query = "SELECT document FROM records WHERE dlbl LIKE 'Depressive disorder' WITH PQR FPD";



// ── Connection ────────────────────────────────────────────────────────────────

$socket = @fsockopen($host, $port, $errno, $errstr, 5);
if (!$socket) die("✗ Cannot connect to GhostQL at $host:$port — $errstr\n");
stream_set_blocking($socket, true);
stream_set_timeout($socket, 30);

// ── Helpers ───────────────────────────────────────────────────────────────────

function readUntilMarker($socket, $marker, $timeout = 15) {
    $buffer = '';
    $end = time() + $timeout;
    stream_set_timeout($socket, 1);
    while (time() < $end) {
        $line = fgets($socket, 4096);
        if ($line !== false) {
            $buffer .= $line;
            if (strpos($buffer, $marker) !== false) break;
        }
        if (feof($socket)) break;
    }
    return $buffer;
}

function sendLine($socket, $text) {
    fwrite($socket, $text . "\n");
    fflush($socket);
}

function parseFileref($ref) {
    // e.g. records_0001.jsonl::line1044::REC-00011044::fpd_04bfabf8::
    $parts = explode('::', rtrim($ref, ':'));
    return [
        'source'  => $parts[0] ?? '-',
        'line'    => isset($parts[1]) ? str_replace('line', '', $parts[1]) : '-',
        'rec_id'  => $parts[2] ?? '-',
        'fpd'     => $parts[3] ?? '-',
    ];
}

// ── Auth ──────────────────────────────────────────────────────────────────────

readUntilMarker($socket, 'Username:');
sendLine($socket, $user);
readUntilMarker($socket, 'Password:');
sendLine($socket, $pass);
$auth = readUntilMarker($socket, '>');

if (strpos($auth, 'ERROR') !== false) {
    die("✗ Authentication failed. Check GHOSTQL_PASS.\n");
}

// ── Query ─────────────────────────────────────────────────────────────────────

echo "\n";
echo "  GhostQL — Query Result\n";
echo "  Query : $query\n";
echo "  Server: $host:$port\n\n";

sendLine($socket, $query);
$raw = readUntilMarker($socket, '>', 60);

// Extract JSON
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

if ($data === null || isset($data[0]['status'])) {
    $msg = $data[0]['message'] ?? 'No results';
    echo "  ⚠  $msg\n\n";
    fclose($socket);
    exit;
}

// ── Table output ──────────────────────────────────────────────────────────────

$total = count($data);
$rows  = [];
foreach ($data as $row) {
    $rows[] = parseFileref($row['document'] ?? '');
}

// Column widths
$w = [
    'row'    => strlen((string)$total),
    'source' => max(6,  max(array_map(fn($r) => strlen($r['source']), $rows))),
    'line'   => max(4,  max(array_map(fn($r) => strlen($r['line']),   $rows))),
    'rec_id' => max(6,  max(array_map(fn($r) => strlen($r['rec_id']), $rows))),
    'fpd'    => max(3,  max(array_map(fn($r) => strlen($r['fpd']),    $rows))),
];

$w['row'] = max($w['row'], 3);

function pad($val, $width) { return str_pad($val, $width); }
function divider($w) {
    return '+' . str_repeat('-', $w['row']+2)
         . '+' . str_repeat('-', $w['source']+2)
         . '+' . str_repeat('-', $w['line']+2)
         . '+' . str_repeat('-', $w['rec_id']+2)
         . '+' . str_repeat('-', $w['fpd']+2)
         . '+';
}

$div = divider($w);

echo $div . "\n";
printf("| %s | %s | %s | %s | %s |\n",
    pad('#',      $w['row']),
    pad('Source', $w['source']),
    pad('Line',   $w['line']),
    pad('Rec ID', $w['rec_id']),
    pad('FPD',    $w['fpd'])
);
echo $div . "\n";

foreach ($rows as $i => $r) {
    printf("| %s | %s | %s | %s | %s |\n",
        pad((string)($i+1),  $w['row']),
        pad($r['source'],    $w['source']),
        pad($r['line'],      $w['line']),
        pad($r['rec_id'],    $w['rec_id']),
        pad($r['fpd'],       $w['fpd'])
    );
}

echo $div . "\n";
echo "  $total row(s) returned\n\n";
echo "  Each Rec ID is a pointer to the source document.\n";
echo "  Your application would use these to fetch the actual content —\n";
echo "  a JSON record, PDF, image, or any ingested file.\n\n";

// ── Close ─────────────────────────────────────────────────────────────────────
sendLine($socket, 'quit');
fclose($socket);
?>
