/**
 * Sets up the logging system in the "Logs" sheet.
 */
function setupLoggingSystem() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let logSheet = ss.getSheetByName("Logs");
  if (!logSheet) {
    logSheet = ss.insertSheet("Logs");

    // Set up headers
    const headers = [
      "Timestamp", "Level", "Action Type", "Entity Type",
      "Name", "PAN", "Broker", "Status", "Details"
    ];

    logSheet.appendRow(headers);

    // Format header row
    const headerRange = logSheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground("#d9ead3")
      .setFontWeight("bold")
      .setWrap(true)
      .setHorizontalAlignment("center");

    // Set column widths
    logSheet.setColumnWidths(1, headers.length, 150);
    logSheet.setColumnWidth(1, 180);  // Timestamp
    logSheet.setColumnWidth(9, 300);  // Details

    // Freeze header row and add filters
    logSheet.setFrozenRows(1);
    headerRange.createFilter();
  }
  return logSheet;
}

/**
 * Logs a general action to the "Logs" sheet.
 */
function logAction(actionType, entityType, name, pan, broker, status, details, level = "INFO") {
  const logSheet = setupLoggingSystem();

  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");

  const newRow = [
    timestamp,
    level,
    actionType,
    entityType,
    name || "",
    pan || "",
    broker || "",
    status,
    details || ""
  ];

  const lastRow = logSheet.getLastRow() + 1;
  const range = logSheet.getRange(lastRow, 1, 1, newRow.length);
  range.setValues([newRow]);

  // Apply color coding based on log level
  const levelCell = logSheet.getRange(lastRow, 2);
  switch (level) {
    case "ERROR":
      levelCell.setBackground("#f4cccc"); // light red
      range.setFontColor("#990000");
      break;
    case "WARNING":
      levelCell.setBackground("#fff2cc"); // light yellow
      break;
    case "INFO":
      levelCell.setBackground("#d9ead3"); // light green
      break;
    case "DEBUG":
      levelCell.setBackground("#cfe2f3"); // light blue
      break;
  }
}

/**
 * Logs errors with detailed context.
 */
function logError(functionName, error, additionalInfo = {}) {
  const errorDetails = {
    function: functionName,
    message: error.message,
    stack: error.stack,
    ...additionalInfo
  };

  logAction(
    "ERROR",
    "System",
    functionName,
    "",
    "",
    "Failed",
    JSON.stringify(errorDetails, null, 2),
    "ERROR"
  );
}

/**
 * Handles and logs API responses, including payloads and responses.
 */
function handleApiResponse(response, operation, payload = null) {
  try {
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();

    // Log API Request Payload
    if (payload) {
      logAction(
        operation,
        "API Request",
        "",
        "",
        "",
        "Sent",
        `Payload: ${JSON.stringify(payload)}`,
        "INFO"
      );
    }

    // Handle API Errors
    if (responseCode !== 200) {
      logAction(
        operation,
        "API Response",
        "",
        "",
        "",
        "Failed",
        `Error (${responseCode}): ${responseText}`,
        "ERROR"
      );
      throw new Error(`API Error: ${responseText}`);
    }

    // Log Successful Response
    logAction(
      operation,
      "API Response",
      "",
      "",
      "",
      "Success",
      `Response: ${responseText}`,
      "INFO"
    );

    return JSON.parse(responseText);
  } catch (error) {
    logError(operation, error);
    throw error;
  }
}

/**
 * Cleans up the "Logs" sheet by keeping only the last 1000 logs.
 */
function cleanupLogs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const logSheet = ss.getSheetByName("Logs");
  if (!logSheet) return;

  const MAX_LOGS = 1000;
  const lastRow = logSheet.getLastRow();

  if (lastRow > MAX_LOGS + 1) { // +1 for header row
    logSheet.deleteRows(2, lastRow - MAX_LOGS - 1);
  }

  // Log the cleanup
  logAction(
    "System Maintenance",
    "Logs",
    "",
    "",
    "",
    "Cleanup",
    `Log cleanup performed. Keeping last ${MAX_LOGS} entries.`,
    "INFO"
  );
}

/**
 * Sets up a daily trigger to clean up logs.
 */
function createLogCleanupTrigger() {
  // Delete existing triggers
  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === 'cleanupLogs') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  // Create new daily trigger
  ScriptApp.newTrigger('cleanupLogs')
    .timeBased()
    .everyDays(1)
    .atHour(1)
    .create();
}

