package com.stickerdrop.app

import android.content.ContentProvider
import android.content.ContentValues
import android.content.UriMatcher
import android.content.res.AssetFileDescriptor
import android.database.Cursor
import android.database.MatrixCursor
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException

/**
 * WhatsApp Sticker ContentProvider
 * Conforms to the official WhatsApp Sticker Specification (Phase E, docs/07-whatsapp-integration.md).
 * Serves metadata cursors and asset files (.webp/.awebp, tray_icon.png) to the WhatsApp application.
 */
class WhatsAppStickerContentProvider : ContentProvider() {

    companion object {
        private const val TAG = "StickerContentProvider"

        // Column constants required by WhatsApp Android SDK
        const val STICKER_PACK_IDENTIFIER_IN_QUERY = "sticker_pack_identifier"
        const val STICKER_PACK_NAME_IN_QUERY = "sticker_pack_name"
        const val STICKER_PACK_PUBLISHER_IN_QUERY = "sticker_pack_publisher"
        const val STICKER_PACK_ICON_IN_QUERY = "sticker_pack_icon"
        const val ANDROID_APP_DOWNLOAD_LINK_IN_QUERY = "android_play_store_link"
        const val IOS_APP_DOWNLOAD_LINK_IN_QUERY = "ios_app_download_link"
        const val PUBLISHER_EMAIL = "publisher_email"
        const val PUBLISHER_WEBSITE = "publisher_website"
        const val PRIVACY_POLICY_WEBSITE = "privacy_policy_website"
        const val LICENSE_AGREEMENT_WEBSITE = "license_agreement_website"
        const val IMAGE_DATA_VERSION = "image_data_version"
        const val AVOID_CACHE = "avoid_cache"
        const val ANIMATED_STICKER_PACK = "animated_sticker_pack"

        const val STICKER_FILE_NAME_IN_QUERY = "sticker_file_name"
        const val STICKER_FILE_EMOJI_IN_QUERY = "sticker_pack_emojis"
        const val STICKER_PACK_ANIMATION_DATA = "sticker_pack_animation_data"

        // UriMatcher Match Codes
        private const val METADATA = 1
        private const val METADATA_PACK = 2
        private const val STICKERS = 3
        private const val STICKERS_ASSET = 4

        private val uriMatcher = UriMatcher(UriMatcher.NO_MATCH)

        private val METADATA_COLUMNS = arrayOf(
            STICKER_PACK_IDENTIFIER_IN_QUERY,
            STICKER_PACK_NAME_IN_QUERY,
            STICKER_PACK_PUBLISHER_IN_QUERY,
            STICKER_PACK_ICON_IN_QUERY,
            ANDROID_APP_DOWNLOAD_LINK_IN_QUERY,
            IOS_APP_DOWNLOAD_LINK_IN_QUERY,
            PUBLISHER_EMAIL,
            PUBLISHER_WEBSITE,
            PRIVACY_POLICY_WEBSITE,
            LICENSE_AGREEMENT_WEBSITE,
            IMAGE_DATA_VERSION,
            AVOID_CACHE,
            ANIMATED_STICKER_PACK
        )

        private val STICKER_COLUMNS = arrayOf(
            STICKER_FILE_NAME_IN_QUERY,
            STICKER_FILE_EMOJI_IN_QUERY,
            STICKER_PACK_ANIMATION_DATA
        )
    }

    override fun onCreate(): Boolean {
        val authority = "${context?.packageName ?: "com.stickerdrop.app"}.stickercontentprovider"
        uriMatcher.addURI(authority, "metadata", METADATA)
        uriMatcher.addURI(authority, "metadata/*", METADATA_PACK)
        uriMatcher.addURI(authority, "stickers/*", STICKERS)
        uriMatcher.addURI(authority, "stickers_asset/*/*", STICKERS_ASSET)
        return true
    }

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?
    ): Cursor? {
        val match = uriMatcher.match(uri)
        Log.d(TAG, "query: uri=$uri, match=$match")

        return when (match) {
            METADATA -> getPacksCursor(null)
            METADATA_PACK -> {
                val packIdentifier = uri.lastPathSegment
                getPacksCursor(packIdentifier)
            }
            STICKERS -> {
                val packIdentifier = uri.lastPathSegment ?: return null
                getStickersCursor(packIdentifier)
            }
            else -> null
        }
    }

    /**
     * Build MatrixCursor for sticker packs metadata
     */
    private fun getPacksCursor(filterPackId: String?): Cursor {
        val cursor = MatrixCursor(METADATA_COLUMNS)

        // Try reading exported contents.json first
        val manifestFile = getManifestFile()
        if (manifestFile.exists()) {
            try {
                val jsonString = manifestFile.readText(Charsets.UTF_8)
                val json = JSONObject(jsonString)
                val packs = json.optJSONArray("sticker_packs")
                if (packs != null) {
                    val androidLink = json.optString("android_play_store_link", "https://play.google.com/store/apps/details?id=com.stickerdrop.app")
                    val iosLink = json.optString("ios_app_store_link", "")

                    for (i in 0 until packs.length()) {
                        val pack = packs.getJSONObject(i)
                        val identifier = pack.getString("identifier")
                        if (filterPackId != null && filterPackId != identifier) continue

                        cursor.addRow(arrayOf(
                            identifier,
                            pack.optString("name", "StickerDrop Pack"),
                            pack.optString("publisher", "StickerDrop User"),
                            pack.optString("tray_image_file", "tray_icon.png"),
                            androidLink,
                            iosLink,
                            pack.optString("publisher_email", "support@stickerdrop.app"),
                            pack.optString("publisher_website", "https://stickerdrop.app"),
                            pack.optString("privacy_policy_website", "https://stickerdrop.app/privacy"),
                            pack.optString("license_agreement_website", "https://stickerdrop.app/terms"),
                            "1", // image_data_version
                            0,   // avoid_cache
                            if (pack.optBoolean("animated_sticker_pack", false)) 1 else 0
                        ))
                    }
                    return cursor
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error reading contents.json: ${e.message}", e)
            }
        }

        // Fallback: Query local SQLite database
        val db = openDatabase()
        if (db != null) {
            try {
                val query = if (filterPackId != null) {
                    "SELECT * FROM packs WHERE identifier = ?"
                } else {
                    "SELECT * FROM packs"
                }
                val args = if (filterPackId != null) arrayOf(filterPackId) else null
                db.rawQuery(query, args).use { c ->
                    while (c.moveToNext()) {
                        cursor.addRow(arrayOf(
                            c.getString(c.getColumnIndexOrThrow("identifier")),
                            c.getString(c.getColumnIndexOrThrow("name")),
                            c.getString(c.getColumnIndexOrThrow("publisher")),
                            "tray_icon.png",
                            "https://play.google.com/store/apps/details?id=com.stickerdrop.app",
                            "",
                            "support@stickerdrop.app",
                            "https://stickerdrop.app",
                            "https://stickerdrop.app/privacy",
                            "https://stickerdrop.app/terms",
                            "1",
                            0,
                            c.getInt(c.getColumnIndexOrThrow("is_animated"))
                        ))
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error querying SQLite packs: ${e.message}", e)
            } finally {
                db.close()
            }
        }

        return cursor
    }

    /**
     * Build MatrixCursor for stickers inside a specific pack
     */
    private fun getStickersCursor(packIdentifier: String): Cursor {
        val cursor = MatrixCursor(STICKER_COLUMNS)

        // Try reading exported contents.json
        val manifestFile = getManifestFile()
        if (manifestFile.exists()) {
            try {
                val json = JSONObject(manifestFile.readText(Charsets.UTF_8))
                val packs = json.optJSONArray("sticker_packs")
                if (packs != null) {
                    for (i in 0 until packs.length()) {
                        val pack = packs.getJSONObject(i)
                        if (pack.getString("identifier") == packIdentifier) {
                            val stickers = pack.optJSONArray("stickers") ?: continue
                            for (j in 0 until stickers.length()) {
                                val sticker = stickers.getJSONObject(j)
                                val fileName = sticker.getString("image_file")
                                val emojisArray = sticker.optJSONArray("emojis")
                                val emojisStr = if (emojisArray != null) {
                                    (0 until emojisArray.length()).joinToString(",") { emojisArray.getString(it) }
                                } else {
                                    "🔥"
                                }
                                cursor.addRow(arrayOf(fileName, emojisStr, null))
                            }
                            return cursor
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error reading stickers from manifest: ${e.message}", e)
            }
        }

        // Fallback: Query SQLite database
        val db = openDatabase()
        if (db != null) {
            try {
                val query = """
                    SELECT s.sha256, s.is_animated, pi.emojis
                    FROM pack_items pi
                    JOIN packs p ON p.id = pi.pack_id
                    JOIN stickers s ON s.id = pi.sticker_id
                    WHERE p.identifier = ?
                    ORDER BY pi.sort_order ASC
                """.trimIndent()
                db.rawQuery(query, arrayOf(packIdentifier)).use { c ->
                    while (c.moveToNext()) {
                        val sha = c.getString(0)
                        val isAnim = c.getInt(1) == 1
                        val emojis = c.getString(2) ?: "🔥"
                        val ext = if (isAnim) "awebp" else "webp"
                        val fileName = "$sha.$ext"
                        cursor.addRow(arrayOf(fileName, emojis, null))
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error querying SQLite stickers: ${e.message}", e)
            } finally {
                db.close()
            }
        }

        return cursor
    }

    /**
     * Serves media file descriptors (.webp, .awebp, tray_icon.png) to WhatsApp
     */
    override fun openAssetFile(uri: Uri, mode: String): AssetFileDescriptor? {
        val match = uriMatcher.match(uri)
        if (match != STICKERS_ASSET) {
            Log.e(TAG, "openAssetFile: Unknown URI pattern: $uri")
            throw FileNotFoundException("Unknown URI pattern: $uri")
        }

        val segments = uri.pathSegments
        if (segments.size < 3) {
            throw FileNotFoundException("Invalid asset URI path: $uri")
        }

        val packIdentifier = segments[segments.size - 2]
        val fileName = segments[segments.size - 1]

        val targetFile = resolveAssetFile(packIdentifier, fileName)
            ?: throw FileNotFoundException("Sticker asset file not found: $packIdentifier/$fileName")

        Log.d(TAG, "Serving asset file: ${targetFile.absolutePath} (${targetFile.length()} bytes)")
        val pfd = ParcelFileDescriptor.open(targetFile, ParcelFileDescriptor.MODE_READ_ONLY)
        return AssetFileDescriptor(pfd, 0, AssetFileDescriptor.UNKNOWN_LENGTH)
    }

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor? {
        return openAssetFile(uri, mode)?.parcelFileDescriptor
    }

    private fun resolveAssetFile(packId: String, fileName: String): File? {
        val filesDir = context?.filesDir ?: return null

        // Location 1: WhatsApp export pack directory
        val inPackDir = File(filesDir, "whatsapp_packs/$packId/$fileName")
        if (inPackDir.exists() && inPackDir.length() > 0) return inPackDir

        // Location 2: App media directory
        val inMediaDir = File(filesDir, "media/$fileName")
        if (inMediaDir.exists() && inMediaDir.length() > 0) return inMediaDir

        // Location 3: If tray_icon.png requested but missing, create synthetic 96x96 PNG
        if (fileName.contains("tray_icon")) {
            val trayFile = File(filesDir, "whatsapp_packs/$packId/tray_icon.png")
            if (!trayFile.exists()) {
                trayFile.parentFile?.mkdirs()
                createSyntheticTrayIcon(trayFile)
            }
            if (trayFile.exists()) return trayFile
        }

        return null
    }

    private fun createSyntheticTrayIcon(file: File) {
        try {
            // Synthetic minimal 96x96 transparent PNG
            val syntheticPng = byteArrayOf(
                0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, // PNG signature
                0x00, 0x00, 0x00, 0x0D, // IHDR length
                0x49, 0x48, 0x44, 0x52, // IHDR
                0x00, 0x00, 0x00, 0x60, // 96 width
                0x00, 0x00, 0x00, 0x60, // 96 height
                0x08, 0x06, 0x00, 0x00, 0x00,
                0xE2.toByte(), 0x98.toByte(), 0x39, 0x99.toByte(), // CRC
                0x00, 0x00, 0x00, 0x00, // IEND length
                0x49, 0x45, 0x4E, 0x44, // IEND
                0xAE.toByte(), 0x42, 0x60, 0x82.toByte() // CRC
            )
            file.writeBytes(syntheticPng)
        } catch (e: Exception) {
            Log.e(TAG, "Failed creating synthetic tray icon: ${e.message}")
        }
    }

    private fun getManifestFile(): File {
        val filesDir = context?.filesDir ?: File("/")
        return File(filesDir, "whatsapp_packs/contents.json")
    }

    private fun openDatabase(): SQLiteDatabase? {
        val ctx = context ?: return null
        val dbPath = ctx.getDatabasePath("stickerdrop.db")
        return if (dbPath.exists()) {
            SQLiteDatabase.openDatabase(dbPath.path, null, SQLiteDatabase.OPEN_READONLY)
        } else {
            null
        }
    }

    override fun getType(uri: Uri): String {
        return when (uriMatcher.match(uri)) {
            METADATA -> "vnd.android.cursor.dir/vnd.com.stickerdrop.app.stickercontentprovider.metadata"
            METADATA_PACK -> "vnd.android.cursor.item/vnd.com.stickerdrop.app.stickercontentprovider.metadata"
            STICKERS -> "vnd.android.cursor.dir/vnd.com.stickerdrop.app.stickercontentprovider.stickers"
            STICKERS_ASSET -> "image/webp"
            else -> "application/octet-stream"
        }
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}
