package com.stinkyweasel.dextilt.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.stinkyweasel.dextilt.gesture.SensorSample

class SensorRepository(
    context: Context,
    private val onSample: (SensorSample, SensorSnapshot) -> Unit
) : SensorEventListener {
    private val manager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val accelerometer = manager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroscope = manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val rotationVector = manager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
    private val gravity = manager.getDefaultSensor(Sensor.TYPE_GRAVITY)

    private var ax = 0f
    private var ay = 0f
    private var az = 0f
    private var gx = 0f
    private var gy = 0f
    private var gz = 0f
    private var rot: FloatArray? = null
    private var running = false

    fun availability(): SensorAvailability = SensorAvailability(
        hasAccelerometer = accelerometer != null,
        hasGyroscope = gyroscope != null,
        hasRotationVector = rotationVector != null,
        hasGravity = gravity != null
    )

    fun start() {
        if (running) return
        running = true
        val rate = 20_000 // microseconds, roughly 50 Hz.
        accelerometer?.let { manager.registerListener(this, it, rate) }
        gyroscope?.let { manager.registerListener(this, it, rate) }
        rotationVector?.let { manager.registerListener(this, it, rate) }
        gravity?.let { manager.registerListener(this, it, rate) }
    }

    fun stop() {
        if (!running) return
        running = false
        manager.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_GRAVITY -> {
                ax = event.values.getOrNull(0) ?: ax
                ay = event.values.getOrNull(1) ?: ay
                az = event.values.getOrNull(2) ?: az
            }
            Sensor.TYPE_GYROSCOPE -> {
                gx = event.values.getOrNull(0) ?: gx
                gy = event.values.getOrNull(1) ?: gy
                gz = event.values.getOrNull(2) ?: gz
            }
            Sensor.TYPE_ROTATION_VECTOR -> rot = event.values.copyOf()
        }
        val snapshot = SensorSnapshot(ax, ay, az, gx, gy, gz, event.timestamp)
        val sample = SensorSample(event.timestamp, ax, ay, az, gx, gy, gz, hasGyro = gyroscope != null, rotationVector = rot)
        onSample(sample, snapshot)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
