function setupActualPortfolioSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheetName = "Actual Portfolio";
  let sheet = ss.getSheetByName(sheetName);

  try {
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    } else {
      sheet.clear();
    }

    // Instructions
    sheet
      .getRange(1, 1, 1, 4)
      .merge()
      .setValue("Instructions: Enter data for single accounts only. Use YYYY-MM-DD format for month-end dates.")
      .setBackground("#AFE1AF")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Headers
    const headers = ["Account ID", "Trading Symbol", "Quantity", "Date"];
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#379d37")
      .setFontColor("#FFFFFF");
    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 150);

    // Data Validation
    const quantityRange = sheet.getRange(3, 3, 1000); // Column C
    const quantityRule = SpreadsheetApp.newDataValidation()
      .requireNumberGreaterThanOrEqualTo(0)
      .setAllowInvalid(false)
      .build();
    quantityRange.setDataValidation(quantityRule);

    const dateRange = sheet.getRange(3, 4, 1000); // Column D
    const dateRule = SpreadsheetApp.newDataValidation()
      .requireDate()
      .setAllowInvalid(false)
      .build();
    dateRange.setDataValidation(dateRule);

    ui.alert("Actual Portfolio sheet is ready. Fill in the data and use 'Save Actual Portfolio' when done.");
    sheet.activate();
  } catch (error) {
    logError("setupActualPortfolioSheet", error);
    ui.alert("Error setting up Actual Portfolio sheet: " + error.message);
  }
}

function setupCashflowsSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheetName = "Cashflows";
  let sheet = ss.getSheetByName(sheetName);

  try {
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    } else {
      sheet.clear();
    }

    // Instructions
    sheet
      .getRange(1, 1, 1, 4)
      .merge()
      .setValue("Instructions: Enter data for single accounts only. Use YYYY-MM-DD format. Cashflow: positive for inflow, negative for outflow.")
      .setBackground("#AFE1AF")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Headers
    const headers = ["Account ID", "Date", "Cashflow", "Tag"];
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#379d37")
      .setFontColor("#FFFFFF");
    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 150);

    // Data Validation
    const dateRange = sheet.getRange(3, 2, 1000); // Column B
    const dateRule = SpreadsheetApp.newDataValidation()
      .requireDate()
      .setAllowInvalid(false)
      .build();
    dateRange.setDataValidation(dateRule);

    const cashflowRange = sheet.getRange(3, 3, 1000); // Column C
    const cashflowRule = SpreadsheetApp.newDataValidation()
      .requireNumber()
      .setAllowInvalid(false)
      .build();
    cashflowRange.setDataValidation(cashflowRule);

    ui.alert("Cashflows sheet is ready. Fill in the data and use 'Save Cashflows' when done.");
    sheet.activate();
  } catch (error) {
    logError("setupCashflowsSheet", error);
    ui.alert("Error setting up Cashflows sheet: " + error.message);
  }
}

function setupExceptionsSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheetName = "Exceptions";
  let sheet = ss.getSheetByName(sheetName);

  try {
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    } else {
      sheet.clear();
    }

    // Instructions
    sheet
      .getRange(1, 1, 1, 2)
      .merge()
      .setValue("Instructions: Enter data for single accounts only. List stocks to ignore in reconciliation.")
      .setBackground("#AFE1AF")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Headers
    const headers = ["Account ID", "Trading Symbol"];
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#379d37")
      .setFontColor("#FFFFFF");
    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 150);

    ui.alert("Exceptions sheet is ready. Fill in the data and use 'Save Exceptions' when done.");
    sheet.activate();
  } catch (error) {
    logError("setupExceptionsSheet", error);
    ui.alert("Error setting up Exceptions sheet: " + error.message);
  }
}



function saveCashflows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName("Cashflows");

  if (!sheet) {
    ui.alert("Cashflows sheet not found.");
    return;
  }

  try {
    const dataRange = sheet.getDataRange();
    const values = dataRange.getValues();
    const dataRows = values.slice(2);

    const data = dataRows
      .filter(row => row.some(cell => cell !== ""))
      .map(row => ({
        account_id: row[0],
        event_date: row[1],
        cashflow: row[2],
        tag: row[3]
      }));

    // Validation
    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      if (!row.account_id || !row.event_date || row.cashflow === "" || !row.tag) {
        ui.alert(`Row ${i + 3}: All fields are required.`);
        return;
      }
      if (typeof row.cashflow !== "number" || isNaN(row.cashflow)) {
        ui.alert(`Row ${i + 3}: Cashflow must be a number.`);
        return;
      }
      if (!isValidDate(row.event_date)) {
        ui.alert(`Row ${i + 3}: Date must be a valid date in YYYY-MM-DD format.`);
        return;
      }
    }

    if (data.length === 0) {
      ui.alert("No data to save.");
      return;
    }

    // Send to API
    const endpoint = "https://your-api.com/manual/cashflows";
    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(data),
      headers: { "Authorization": "Bearer " + ScriptApp.getOAuthToken() }
    };

    const response = UrlFetchApp.fetch(endpoint, options);
    handleApiResponse(response, "Save Cashflows", data);
    ui.alert("Cashflows saved successfully!");
  } catch (error) {
    logError("saveCashflows", error);
    ui.alert("Error saving Cashflows: " + error.message);
  }
}

function saveExceptions() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName("Exceptions");

  if (!sheet) {
    ui.alert("Exceptions sheet not found.");
    return;
  }

  try {
    const dataRange = sheet.getDataRange();
    const values = dataRange.getValues();
    const dataRows = values.slice(2);

    const data = dataRows
      .filter(row => row.some(cell => cell !== ""))
      .map(row => ({
        account_id: row[0],
        trading_symbol: row[1]
      }));

    // Validation
    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      if (!row.account_id || !row.trading_symbol) {
        ui.alert(`Row ${i + 3}: All fields are required.`);
        return;
      }
    }

    if (data.length === 0) {
      ui.alert("No data to save.");
      return;
    }

    // Send to API
    const endpoint = "https://your-api.com/manual/exceptions";
    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(data),
      headers: { "Authorization": "Bearer " + ScriptApp.getOAuthToken() }
    };

    const response = UrlFetchApp.fetch(endpoint, options);
    handleApiResponse(response, "Save Exceptions", data);
    ui.alert("Exceptions saved successfully!");
  } catch (error) {
    logError("saveExceptions", error);
    ui.alert("Error saving Exceptions: " + error.message);
  }
}

function saveCashflows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName("Cashflows Input");

  if (!sheet) {
    ui.alert("Cashflows sheet not found.");
    return;
  }

  try {
    const dataRange = sheet.getDataRange();
    const values = dataRange.getValues();
    const dataRows = values.slice(2);

    const data = dataRows
      .filter(row => row.some(cell => cell !== ""))
      .map(row => ({
        owner_type: row[0],
        account_id: row[1],
        event_date: row[2],
        cashflow: row[3],
        tag: row[4]
      }));

    // Validation
    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      if (!row.owner_type || !row.account_id || !row.event_date || row.cashflow === "" || !row.tag) {
        ui.alert(`Row ${i + 3}: All fields are required.`);
        return;
      }
      if (!["single", "joint"].includes(row.owner_type)) {
        ui.alert(`Row ${i + 3}: Owner Type must be 'single' or 'joint'.`);
        return;
      }
      if (typeof row.cashflow !== "number" || isNaN(row.cashflow)) {
        ui.alert(`Row ${i + 3}: Cashflow must be a number.`);
        return;
      }
      if (!isValidDate(row.event_date)) {
        ui.alert(`Row ${i + 3}: Date must be a valid date in YYYY-MM-DD format.`);
        return;
      }
    }

    if (data.length === 0) {
      ui.alert("No data to save.");
      return;
    }

    // Send to API
    const endpoint = "https://your-api.com/manual/cashflows"; // Replace with actual endpoint
    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(data),
      headers: { "Authorization": "Bearer " + ScriptApp.getOAuthToken() }
    };

    const response = UrlFetchApp.fetch(endpoint, options);
    handleApiResponse(response, "Save Cashflows", data);
    ui.alert("Cashflows saved successfully!");
  } catch (error) {
    logError("saveCashflows", error);
    ui.alert("Error saving Cashflows: " + error.message);
  }
}

function isValidDate(dateStr) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return false;
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

function isValidMonthEndDate(dateStr) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return false;
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const lastDay = new Date(year, month, 0).getDate();
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === lastDay;
}