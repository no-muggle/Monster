package com.example.smssync.sms

/**
 * Extracts verification codes from SMS message bodies.
 *
 * Uses a multi-strategy ordered regex pipeline. The first matching
 * strategy wins. Common false positives (phone numbers, years, amounts)
 * are filtered out.
 */
object CodeExtractor {

    /** Ordered list of extraction strategies. First match wins. */
    private val STRATEGIES = listOf(
        // Strategy 1: "验证码：123456" or "验证码:123456"
        Regex("""验证码[：:]\s*(\d{4,8})"""),
        // Strategy 2: "验证码" followed by short non-digit separator then digits
        Regex("""验证码\D{0,10}(\d{4,8})"""),
        // Strategy 3: "短信口令" (enterprise SMS common pattern)
        Regex("""短信口令\D{0,10}(\d{4,8})"""),
        // Strategy 4: "口令" (password/code — e.g., "口令562407")
        Regex("""口令\D{0,10}(\d{4,8})"""),
        // Strategy 5: Digits followed by "验证码" (some services put code first)
        Regex("""(\d{4,8})\D{0,5}验证码"""),
        // Strategy 6: English patterns (code, OTP, PIN, verification)
        Regex("""(?:code|otp|pin|verification|verify)\D{0,10}(\d{4,8})""",
            RegexOption.IGNORE_CASE),
        // Strategy 7: "动态码" (dynamic code — used by some Chinese services)
        Regex("""动态码\D{0,10}(\d{4,8})"""),
        // Strategy 8: "校验码" (some services use this term)
        Regex("""校验码\D{0,10}(\d{4,8})"""),
        // Strategy 9: "安全码" / "安全口令"
        Regex("""安全(?:码|口令)\D{0,10}(\d{4,8})"""),
        // Strategy 10: "授权码"
        Regex("""授权码\D{0,10}(\d{4,8})"""),
        // Strategy 11: Standalone 4-8 digit number as last resort
        Regex("""(?<!\d)(\d{4,8})(?!\d)"""),
    )

    /**
     * Extract a verification code from an SMS body.
     *
     * @param smsBody The full SMS message body.
     * @return The extracted code, or null if none found.
     */
    fun extract(smsBody: String): String? {
        for (regex in STRATEGIES) {
            val match = regex.find(smsBody)
            if (match != null) {
                val code = match.groupValues[1]
                if (!isFalsePositive(code, smsBody)) {
                    return code
                }
            }
        }
        return null
    }

    /**
     * Check if a matched number is likely a false positive.
     */
    private fun isFalsePositive(code: String, body: String): Boolean {
        // Phone number: 11 digits starting with 1 (Chinese mobile)
        if (code.length == 11 && code.startsWith("1")) return true

        // Year: 19xx or 20xx
        if (code.length == 4 &&
            (code.startsWith("19") || code.startsWith("20"))) return true

        // Currency: preceded by yen, dollar or yuan sign
        if (Regex("""[${'$'}¥￥元]\s*${Regex.escape(code)}""").containsMatchIn(body))
            return true

        // Time pattern: HH:MM format (e.g., "10:30" not really 5 digits,
        // but 4-digit times like "1030" are unlikely in SMS)

        return false
    }

    /** Regex for extracting sender name from 【Name】 brackets in SMS body. */
    private val SENDER_PATTERN = Regex("""【(.+?)】""")

    /**
     * Try to extract a human-readable sender name from the SMS body.
     * Many Chinese services use 【Service Name】 format at the beginning.
     *
     * @param smsBody The full SMS body.
     * @return The extracted sender name, or null if not found.
     */
    fun extractSenderName(smsBody: String): String? {
        return SENDER_PATTERN.find(smsBody)?.groupValues?.get(1)
    }
}
