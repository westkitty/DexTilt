package com.stinkyweasel.dextilt.ui

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

class Feedback(context: Context) {
    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= 31) {
        (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

    fun tick() = vibrate(longArrayOf(0, 35), intArrayOf(0, 80))
    fun success() = vibrate(longArrayOf(0, 45, 60, 65), intArrayOf(0, 120, 0, 160))
    fun failure() = vibrate(longArrayOf(0, 120), intArrayOf(0, 180))

    private fun vibrate(timings: LongArray, amplitudes: IntArray) {
        val v = vibrator ?: return
        if (!v.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(timings, amplitudes, -1))
        else @Suppress("DEPRECATION") v.vibrate(timings.sum())
    }
}
