package com.stickerdrop.app

import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    companion object {
        private const val CHANNEL = "com.stickerdrop.app/whatsapp_intent"
        private const val EXTRA_STICKER_PACK_ID = "sticker_pack_id"
        private const val EXTRA_STICKER_PACK_AUTHORITY = "sticker_pack_authority"
        private const val EXTRA_STICKER_PACK_NAME = "sticker_pack_name"
        private const val ACTION_ENABLE_STICKER_PACK = "com.whatsapp.intent.action.ENABLE_STICKER_PACK"
        private const val ADD_PACK_REQUEST_CODE = 200
        private const val WHATSAPP_PACKAGE = "com.whatsapp"
        private const val WHATSAPP_BUSINESS_PACKAGE = "com.whatsapp.w4b"
    }

    private var pendingResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "addStickerPack" -> {
                    val packId = call.argument<String>("packIdentifier")
                    val packName = call.argument<String>("packName")
                    val authority = call.argument<String>("authority")
                        ?: "${applicationContext.packageName}.stickercontentprovider"

                    if (packId.isNullOrEmpty() || packName.isNullOrEmpty()) {
                        result.error("INVALID_ARGUMENTS", "packIdentifier and packName must not be empty", null)
                        return@setMethodCallHandler
                    }

                    addPackToWhatsApp(packId, packName, authority, result)
                }
                "isPackageInstalled" -> {
                    val packageName = call.argument<String>("packageName") ?: WHATSAPP_PACKAGE
                    result.success(isPackageInstalled(packageName))
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }

    private fun isPackageInstalled(packageName: String): Boolean {
        return try {
            packageManager.getPackageInfo(packageName, PackageManager.GET_ACTIVITIES)
            true
        } catch (e: PackageManager.NameNotFoundException) {
            false
        }
    }

    private fun addPackToWhatsApp(
        packId: String,
        packName: String,
        authority: String,
        result: MethodChannel.Result
    ) {
        val isWaInstalled = isPackageInstalled(WHATSAPP_PACKAGE)
        val isWaBusinessInstalled = isPackageInstalled(WHATSAPP_BUSINESS_PACKAGE)

        if (!isWaInstalled && !isWaBusinessInstalled) {
            result.error("WHATSAPP_NOT_INSTALLED", "Neither WhatsApp nor WhatsApp Business is installed on this device", null)
            return
        }

        val targetPackage = if (isWaInstalled) WHATSAPP_PACKAGE else WHATSAPP_BUSINESS_PACKAGE

        val intent = Intent().apply {
            action = ACTION_ENABLE_STICKER_PACK
            putExtra(EXTRA_STICKER_PACK_ID, packId)
            putExtra(EXTRA_STICKER_PACK_AUTHORITY, authority)
            putExtra(EXTRA_STICKER_PACK_NAME, packName)
            `package` = targetPackage
        }

        try {
            pendingResult = result
            startActivityForResult(intent, ADD_PACK_REQUEST_CODE)
        } catch (e: ActivityNotFoundException) {
            pendingResult = null
            result.error("ACTIVITY_NOT_FOUND", "Could not start WhatsApp sticker import intent: ${e.message}", null)
        } catch (e: Exception) {
            pendingResult = null
            result.error("EXPORT_FAILED", "Failed to add pack to WhatsApp: ${e.message}", null)
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ADD_PACK_REQUEST_CODE) {
            val result = pendingResult
            pendingResult = null
            if (result != null) {
                result.success(resultCode == RESULT_OK || resultCode == RESULT_CANCELED)
            }
        }
    }
}
