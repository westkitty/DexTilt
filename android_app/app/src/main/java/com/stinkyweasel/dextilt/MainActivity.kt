package com.stinkyweasel.dextilt

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DexTiltTheme {
                val vm: DexTiltViewModel = viewModel()
                DexTiltRoot(vm)
            }
        }
    }
}

@Composable
fun DexTiltTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = androidx.compose.material3.darkColorScheme(
            primary = Color(0xFFD7E3FF),
            secondary = Color(0xFF8EE99A),
            background = Color(0xFF0B0D10),
            surface = Color(0xFF151922),
            error = Color(0xFFFF6B6B)
        ),
        content = content
    )
}

@Composable
fun DexTiltRoot(vm: DexTiltViewModel) {
    val ui = vm.ui
    var tab by rememberSaveable { mutableStateOf("Home") }
    val tabs = listOf("Home", "Pair", "Calibrate", "Train", "Test", "Debug")
    Surface(Modifier.fillMaxSize(), color = Color(0xFF0B0D10)) {
        Column(Modifier.fillMaxSize().padding(16.dp)) {
            Text("DexTilt", fontSize = 34.sp, fontWeight = FontWeight.Bold, color = Color(0xFFEFF6FF))
            Text("Local Android-to-Mac motion command layer", color = Color(0xFF94A3B8))
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                tabs.forEach { name ->
                    if (tab == name) Button(onClick = { tab = name }, contentPadding = ButtonDefaults.TextButtonContentPadding) { Text(name) }
                    else OutlinedButton(onClick = { tab = name }, contentPadding = ButtonDefaults.TextButtonContentPadding) { Text(name) }
                }
            }
            Spacer(Modifier.height(12.dp))
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                StatusCard(vm)
                when (tab) {
                    "Home" -> HomeScreen(vm)
                    "Pair" -> PairScreen(vm)
                    "Calibrate" -> CalibrationScreen(vm)
                    "Train" -> TrainingScreen(vm)
                    "Test" -> GestureTestScreen(vm)
                    "Debug" -> DebugScreen(vm)
                }
            }
        }
    }
}

@Composable
fun StatusCard(vm: DexTiltViewModel) {
    val ui = vm.ui
    DexCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(12.dp).height(12.dp).background(stateColor(ui.phase.label), RoundedCornerShape(99.dp)))
            Spacer(Modifier.width(10.dp))
            Column {
                Text(ui.phase.label, fontWeight = FontWeight.Bold, color = Color.White)
                Text(if (ui.pairing != null) "Paired to ${ui.pairing.host}:${ui.pairing.port}" else "No Mac paired", color = Color(0xFF94A3B8))
            }
        }
        Spacer(Modifier.height(10.dp))
        Text("Last result: ${ui.lastResult}", color = Color(0xFFD7E3FF))
        ui.lastError?.let { Text("Error: $it", color = Color(0xFFFF6B6B)) }
        ui.lastConfidence?.let { Text("Confidence: $it", color = Color(0xFF8EE99A), fontFamily = FontFamily.Monospace) }
    }
}

@Composable
fun HomeScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    DexCard(title = "Control") {
        Text("DexTilt only listens while you explicitly arm it. Start face down and stable before performing the trained gesture.", color = Color(0xFFCBD5E1))
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(onClick = { vm.arm() }, enabled = !ui.armed) { Text("Hold / tap to arm") }
            OutlinedButton(onClick = { vm.disarm() }) { Text("Disarm") }
        }
        if (ui.confirmationRequired) {
            Spacer(Modifier.height(10.dp))
            Button(onClick = { vm.confirmMediumConfidence() }) { Text("Confirm medium-confidence gesture") }
        }
    }
    DexCard(title = "Manual actions") {
        Text("Use these first. Do not debug gesture recognition until manual commands work.", color = Color(0xFF94A3B8))
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.testHealth() }) { Text("Health check") }
            Button(onClick = { vm.sendManual("notify_test") }) { Text("Test Mac notification") }
        }
        Spacer(Modifier.height(8.dp))
        Button(onClick = { vm.sendManual("open_gpt_default_browser") }, modifier = Modifier.fillMaxWidth()) { Text("Open ChatGPT") }
    }
}

@Composable
fun PairScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    val scanLauncher = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let { vm.handleQr(it) }
    }
    DexCard(title = "Pair with Mac") {
        Text("Open the Mac dashboard, scan the QR code, then test Health, Notification, and Open ChatGPT.", color = Color(0xFFCBD5E1))
        Spacer(Modifier.height(10.dp))
        Button(onClick = {
            val options = ScanOptions()
                .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                .setPrompt("Scan DexTilt Mac Receiver QR")
                .setBeepEnabled(false)
                .setOrientationLocked(false)
            scanLauncher.launch(options)
        }) { Text("Scan Mac QR") }
        Spacer(Modifier.height(14.dp))
        Text("Manual fallback", fontWeight = FontWeight.Bold)
        OutlinedTextField(value = ui.manualHost, onValueChange = vm::updateManualHost, label = { Text("Host or Tailscale name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = ui.manualPort, onValueChange = vm::updateManualPort, label = { Text("Port") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = ui.manualReceiverId, onValueChange = vm::updateManualReceiverId, label = { Text("Receiver ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = ui.manualToken, onValueChange = vm::updateManualToken, label = { Text("One-time pairing token") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.pairManual() }) { Text("Pair manually") }
            OutlinedButton(onClick = { vm.testHealth() }) { Text("Test connection") }
        }
    }
}

@Composable
fun CalibrationScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    val step = vm.calibrationSteps.getOrNull(ui.calibrationStepIndex)
    DexCard(title = "Mac-guided calibration") {
        Text("The Mac dashboard shows progress. Android sends signed calibration updates after pairing.", color = Color(0xFFCBD5E1))
        Spacer(Modifier.height(10.dp))
        if (step != null && !ui.calibrationComplete) {
            Text("Step ${ui.calibrationStepIndex + 1}/${vm.calibrationSteps.size}: ${step.label}", fontWeight = FontWeight.Bold)
            Text(step.instruction, color = Color(0xFFD7E3FF))
            Spacer(Modifier.height(8.dp))
            Button(onClick = { vm.runCalibrationStep() }) { Text("Send step detected") }
        } else {
            Text("Calibration complete.", color = Color(0xFF8EE99A), fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun TrainingScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    DexCard(title = "Train first gesture") {
        Text("Start with the phone face down and stable. Record a clear motion lasting about 0.8 to 2.5 seconds.", color = Color(0xFFCBD5E1))
        Spacer(Modifier.height(8.dp))
        Text("Face-down stable: ${if (ui.faceDownStable) "yes" else "no"}", color = if (ui.faceDownStable) Color(0xFF8EE99A) else Color(0xFFFFD166))
        Text("Samples: ${ui.recordingCount}", fontFamily = FontFamily.Monospace)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.startRecording() }) { Text("Record") }
            Button(onClick = { vm.saveRecording() }) { Text("Save gesture") }
        }
        Spacer(Modifier.height(10.dp))
        Text("Sensitivity", fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("strict", "normal", "relaxed").forEach { s ->
                if (ui.sensitivity == s) Button(onClick = { vm.setSensitivity(s) }) { Text(s) }
                else OutlinedButton(onClick = { vm.setSensitivity(s) }) { Text(s) }
            }
        }
    }
    LiveSensorCard(vm)
}

@Composable
fun GestureTestScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    DexCard(title = "Test gesture locally") {
        Text("This screen scores your gesture without sending a Mac command.", color = Color(0xFFCBD5E1))
        Text("Active gesture: ${ui.activeGesture?.name ?: "None"}", color = Color(0xFFD7E3FF))
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.startLocalGestureTest() }) { Text("Start local test") }
            Button(onClick = { vm.finishLocalGestureTest() }) { Text("Score test") }
        }
    }
    LiveSensorCard(vm)
}

@Composable
fun DebugScreen(vm: DexTiltViewModel) {
    val ui = vm.ui
    DexCard(title = "Sensors") {
        Text(ui.sensorAvailability.userText(), fontFamily = FontFamily.Monospace, color = Color(0xFFD7E3FF))
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.startSensors() }) { Text("Start sensor preview") }
            OutlinedButton(onClick = { vm.stopSensors() }) { Text("Stop sensors") }
        }
    }
    LiveSensorCard(vm)
    DexCard(title = "Local logs") {
        ui.logs.take(30).forEach { Text(it, color = Color(0xFFCBD5E1), fontFamily = FontFamily.Monospace, fontSize = 12.sp) }
    }
    DexCard(title = "Reset") {
        Text("This deletes local pairing and gesture templates on the phone only. Reset the Mac receiver separately if needed.", color = Color(0xFFFFD166))
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { vm.resetPairing() }) { Text("Reset Android pairing and gestures") }
    }
}

@Composable
fun LiveSensorCard(vm: DexTiltViewModel) {
    val s = vm.ui.sensorSnapshot
    DexCard(title = "Live sensor display") {
        Text("accel x=${"%.2f".format(s.ax)} y=${"%.2f".format(s.ay)} z=${"%.2f".format(s.az)}", fontFamily = FontFamily.Monospace)
        Text("gyro  x=${"%.2f".format(s.gx)} y=${"%.2f".format(s.gy)} z=${"%.2f".format(s.gz)}", fontFamily = FontFamily.Monospace)
    }
}

@Composable
fun DexCard(title: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF151922)),
        shape = RoundedCornerShape(18.dp)
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            if (title != null) Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color.White)
            content()
        }
    }
}

fun stateColor(label: String): Color = when {
    label.contains("accepted", ignoreCase = true) || label.contains("ready", ignoreCase = true) || label.contains("paired", ignoreCase = true) -> Color(0xFF8EE99A)
    label.contains("error", ignoreCase = true) || label.contains("rejected", ignoreCase = true) -> Color(0xFFFF6B6B)
    label.contains("armed", ignoreCase = true) || label.contains("record", ignoreCase = true) -> Color(0xFFFFD166)
    else -> Color(0xFF94A3B8)
}
