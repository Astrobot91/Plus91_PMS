function viewClients() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    // Log the start of creating/clearing the read-only sheet
    logAction(
      "Create Sheet",
      "View Clients",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Client Details' sheet",
      "INFO"
    );

    // 1) Create or clear the "Client Details" sheet
    let sheetName = "Client Details";
    let sheet = ss.getSheetByName(sheetName);

    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
      logAction(
        "Create Sheet",
        "Client Details",
        "",
        "",
        "",
        "Success",
        "Created new 'Client Details' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Client Details",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Client Details' sheet",
        "INFO"
      );
    }

    // 2) Add a read-only notice at the top (merge columns as needed)
    const totalColumns = 19; // Adjust if you have fewer or more columns
    sheet
      .getRange(1, 1, 1, totalColumns)
      .merge()
      .setValue("Client Details Sheet: [Read Only]")
      .setBackground("#a4c2f4")
      .setFontColor("#000000")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    // 3) Create column headers in the second row
    const headers = [
      "Client ID",
      "Client Name",
      "Account ID",
      "Broker Name",
      "Broker Code",
      "Broker Password",
      "PAN No.",
      "Country Code",
      "Phone No.",
      "Email ID",
      "Address",
      "Account Start Date",
      "Distributor",
      "Onboard Status",
      "Type",
      "Alias Name",
      "Alias Phone No.",
      "Alias Address",
      "Created At"
    ];

    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#3c78d8")
      .setFontColor("#FFFFFF");

    sheet.setFrozenRows(2);

    // Set a uniform width for all columns so they are evenly spaced
    sheet.setColumnWidths(1, headers.length, 130);

    // 4) Fetch client data from the endpoint
    const endpoint = "http://15.207.59.232:8000/clients/list"; // Replace if needed
    let clientData = [];

    try {
      logAction(
        "Fetch Data",
        "Clients",
        "",
        "",
        "",
        "Started",
        "Fetching client data from " + endpoint,
        "INFO"
      );

      const response = UrlFetchApp.fetch(endpoint);
      const statusCode = response.getResponseCode();

      if (statusCode === 200) {
        clientData = JSON.parse(response.getContentText());
        logAction(
          "Fetch Data",
          "Clients",
          "",
          "",
          "",
          "Success",
          `Fetched ${clientData.length} clients from ${endpoint}`,
          "INFO"
        );
      } else {
        logAction(
          "Fetch Data",
          "Clients",
          "",
          "",
          "",
          "Failed",
          "Status code: " + statusCode,
          "ERROR"
        );
        ui.alert("Failed to fetch client data. Status code: " + statusCode);
      }
    } catch (error) {
      logError("viewClients:FetchData", error);
      ui.alert("Error fetching client data: " + error.message);
    }

    // 5) Populate the sheet if we have data
    if (clientData.length > 0) {
      const rowData = clientData.map(client => [
        client.client_id || "",
        client.client_name || "",
        client.account_id || "",
        client.broker_name || "",
        client.broker_code || "",
        client.broker_passwd || "",
        client.pan_no || "",
        client.country_code || "",
        client.phone_no || "",
        client.email_id || "",
        client.addr || "",
        client.acc_start_date || "",
        client.distributor_name || "",
        client.onboard_status || "",
        client.type || "",
        client.alias_name || "",
        client.alias_phone_no || "",
        client.alias_addr || "",
        client.created_at || ""
      ]);

      sheet
        .getRange(3, 1, rowData.length, headers.length)
        .setValues(rowData);

      logAction(
        "Populate Sheet",
        "Client Details",
        "",
        "",
        "",
        "Success",
        `Populated ${rowData.length} rows with client data`,
        "INFO"
      );
    } else {
      logAction(
        "Populate Sheet",
        "Client Details",
        "",
        "",
        "",
        "Success",
        "No client data found to display",
        "INFO"
      );
    }

    // 6) Color alternate rows (white for first row, #F3F3F3 for second, etc.)
    const startRow = 3; // first row of data
    const numRows = sheet.getLastRow() - (startRow - 1);
    for (let i = 0; i < numRows; i++) {
      // sheet row index
      const rowIndex = startRow + i;
      // even-numbered block => #FFFFFF, odd => #F3F3F3
      if (i % 2 === 0) {
        sheet
          .getRange(rowIndex, 1, 1, headers.length)
          .setBackground("#FFFFFF");
      } else {
        sheet
          .getRange(rowIndex, 1, 1, headers.length)
          .setBackground("#F8F8F8");
      }
    }

    // 7) Make all data rows read-only by protecting them
    // try {
    //   const protectionRange = sheet.getRange(
    //     startRow,
    //     1,
    //     sheet.getMaxRows() - 2,
    //     headers.length
    //   );
    //   const protection = protectionRange.protect();
    //   protection.setDescription("Protected range for read-only sheet");

    //   if (protection.canDomainEdit()) {
    //     protection.setDomainEdit(false);
    //   }

    //   // Remove existing editors to ensure it's fully read-only
    //   const editors = protection.getEditors();
    //   if (editors && editors.length > 0) {
    //     protection.removeEditors(editors);
    //   }
    // } catch (protError) {
    //   // We'll log the protection error, but not throw
    //   logAction(
    //     "Set Protection",
    //     "Client Details",
    //     "",
    //     "",
    //     "",
    //     "Failed",
    //     "Unable to protect sheet range. " + protError.message,
    //     "ERROR"
    //   );
    // }

    // Notify user that the sheet is ready
    // ui.alert(
    //   "Client Details Sheet Ready",
    //   "This is a read-only sheet showing all clients.",
    //   ui.ButtonSet.OK
    // );

    logAction(
      "Create Sheet",
      "View Clients",
      "",
      "",
      "",
      "Completed",
      "'Client Details' sheet successfully populated",
      "INFO"
    );

    sheet.activate();
  } catch (error) {
    // Log and notify major errors
    logError("viewClients", error);
    ui.alert(
      "Error creating or populating the 'Client Details' sheet: " + error.message
    );
  }
}


function addClients() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    logAction("Create Sheet", "Clients", "", "", "", "Started", "Initializing Add Clients sheet", "INFO");

    let sheet = ss.getSheetByName("Add Clients");
    if (!sheet) {
      sheet = ss.insertSheet("Add Clients");
      logAction("Create Sheet", "Clients", "", "", "", "Success", "Created new 'Add Clients' sheet", "INFO");
    } else {
      sheet.clear();
      logAction("Create Sheet", "Clients", "", "", "", "Success", "Cleared existing 'Add Clients' sheet", "INFO");
    }

    // Instructions and Headers
    sheet
      .getRange(1, 1, 1, 15)
      .merge()
      .setValue(
        "Instructions: Fields 'Client Name', 'Broker Name' and 'Pan No.' are required.\n" +
        "Dates in YYYY-MM-DD format.\nUse dropdown for 'Broker Name' and 'Distributor'."
      )
      .setBackground("#AFE1AF")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Headers (15 columns)
    const headers = [
      "Client Name", 
      "Broker Name", 
      "Broker Code", 
      "Broker Password", 
      "Email ID",
      "Pan No.", 
      "Country Code", 
      "Phone No.", 
      "Address", 
      "Account Start Date",
      "Distributor", 
      "Alias Name", 
      "Alias Phone No.", 
      "Alias Address",
      "Type"
    ];

    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#379d37")
      .setFontColor("#FFFFFF");
    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 150);

    // Fetch Brokers and Distributors
    let brokers = [];
    let distributors = [];
    try {
      brokers = getBrokersList();
      logAction("Fetch Data", "Brokers", "", "", "", "Success", `Fetched ${brokers.length} brokers`, "INFO");
    } catch (error) {
      logError("getBrokersList", error);
      ui.alert("Error fetching brokers: " + error.message);
    }

    try {
      distributors = getDistributorsList();
      logAction("Fetch Data", "Distributors", "", "", "", "Success", `Fetched ${distributors.length} distributors`, "INFO");
    } catch (error) {
      logError("getDistributorsList", error);
      ui.alert("Error fetching distributors: " + error.message);
    }

    // Apply Dropdowns for Brokers
    if (brokers.length > 0) {
      const brokerRange = sheet.getRange(3, 2, 1000); // Column B
      const brokerRule = SpreadsheetApp.newDataValidation()
        .requireValueInList(brokers, true)
        .setAllowInvalid(false)
        .build();
      brokerRange.setDataValidation(brokerRule);
    }

    // Apply Dropdowns for Distributors
    if (distributors.length > 0) {
      const distributorRange = sheet.getRange(3, 11, 1000); // Column K=11, L=12, etc.
      const distributorRule = SpreadsheetApp.newDataValidation()
        .requireValueInList(distributors, true)
        .setAllowInvalid(false)
        .build();
      distributorRange.setDataValidation(distributorRule);
    }

    ui.alert(
      "Add Client sheet created",
      "Fill in details. Use 'Save Changes' when done.",
      ui.ButtonSet.OK
    );

    logAction("Create Sheet", "Clients", "", "", "", "Completed", "Add Clients sheet setup complete", "INFO");
    sheet.activate();
  } catch (error) {
    logError("addClients", error);
    ui.alert("Error creating Add Clients sheet: " + error.message);
  }
}

function addClientsSave() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetName = "Add Clients";
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Sheet 'Add Clients' not found.");
    return;
  }

  // Read all rows below the header (assuming header is in row 2)
  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    SpreadsheetApp.getUi().alert("No data found on 'Add Clients' sheet.");
    return;
  }

  // For example, read 16 columns as in your existing code
  const dataRange = sheet.getRange(3, 1, lastRow - 2, 16);
  const data = dataRange.getValues();

  // We'll store valid vs. invalid
  const validRows = [];
  const invalidRows = [];

  // If you keep a brokers list:
  let brokers = [];
  try {
    brokers = getBrokersList(); // Your function that fetches broker names
    logAction("Fetch Data", "Brokers", "", "", "", "Success", `Fetched ${brokers.length} brokers`, "INFO");
  } catch (error) {
    logError("getBrokersList", error);
    SpreadsheetApp.getUi().alert("Error fetching brokers: " + error.message);
  }

  // Simple PAN regex
  const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;

  logAction("Save Changes", "Clients", "", "", "", "Started", "Validating client data", "INFO");

  data.forEach((row, idx) => {
    // Using your 16 columns from the example
    const [
      clientName, brokerName, brokerCode, brokerPasswd, emailId,
      panNo, countryCode, phoneNo, addr, accStartDate,
      distributorName, aliasName, aliasPhoneNo, aliasAddr, type
    ] = row.map(cell => cell ? cell.toString().trim() : '');

    // Validate
    let errors = [];

    // Required Fields
    if (!clientName) errors.push("Client Name is required.");
    if (!brokerName || !brokers.includes(brokerName)) errors.push("Valid Broker Name is required.");
    if (!panNo || !panRegex.test(panNo)) errors.push("PAN No. is invalid.");

    // Numeric checks
    const numericPhoneNo = phoneNo ? phoneNo.toString() : null;
    const numericCountryCode = countryCode ? countryCode.toString() : null;
    if (numericPhoneNo !== null && (isNaN(numericPhoneNo) || numericPhoneNo.length > 15)) {
      errors.push("Phone No. must be numeric and ≤15 digits.");
    }
    if (numericCountryCode !== null && (isNaN(numericCountryCode) || numericCountryCode.length > 3)) {
      errors.push("Country Code must be numeric and ≤3 digits.");
    }

    // Date parse (if needed)
    let formattedDate = "";
    if (accStartDate) {
      try {
        formattedDate = formatDate(accStartDate); 
      } catch (e) {
        errors.push(`Invalid Date: ${e.message}`);
      }
    }

    if (errors.length === 0) {
      // Valid row
      validRows.push({
        client_name: clientName,
        broker_name: brokerName,
        broker_code: brokerCode,
        broker_passwd: brokerPasswd,
        email_id: emailId,
        pan_no: panNo,
        country_code: numericCountryCode,
        phone_no: numericPhoneNo,
        addr: addr,
        acc_start_date: formattedDate,
        distributor_name: distributorName,
        alias_name: aliasName,
        alias_phone_no: aliasPhoneNo,
        alias_addr: aliasAddr,
        type: type
      });
      logAction("Validation", "Client", clientName, panNo, brokerName, "Valid", "Client passed validation", "INFO");
    } else {
      // Invalid row
      invalidRows.push({ row: idx + 3, errors });
      logAction("Validation", "Client", clientName, panNo, brokerName, "Invalid", `Row ${idx + 3} errors: ${errors.join("; ")}`, "WARNING");
    }
  });

  // If any invalid rows, show an alert and stop
  if (invalidRows.length > 0) {
    let errorMsg = "Validation Errors:\n";
    invalidRows.forEach(err => {
      errorMsg += `Row ${err.row}: ${err.errors.join("; ")}\n`;
    });
    SpreadsheetApp.getUi().alert(errorMsg);
    return;
  }

  // If no valid rows, nothing to send
  if (validRows.length === 0) {
    SpreadsheetApp.getUi().alert("No valid data to submit.");
    return;
  }

  // Log we are about to send
  logAction("Validation", "Client", "", "", "", "Valid", JSON.stringify(validRows), "INFO");

  // Send to backend
  const url = "http://15.207.59.232:8000/clients/add"; 
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(validRows),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const statusCode = response.getResponseCode();
    const contentText = response.getContentText();

    // Log the raw response
    logAction("Add Clients", "API Response", "", "", "", 
              statusCode === 200 ? "Success" : "Failed",
              `Response: ${contentText}`, 
              statusCode === 200 ? "INFO" : "ERROR");

    if (statusCode !== 200) {
      SpreadsheetApp.getUi().alert("Error adding clients: " + contentText);
      return;
    }

    // Parse partial success
    const resultObj = JSON.parse(contentText);
    // resultObj => { total_rows, processed_rows, results: [ { row_index, status, detail, client_id } ... ] }

    // We'll log each row result
    let failCount = 0;
    let failMessages = [];
    let successCount = 0;

    resultObj.results.forEach(r => {
      if (r.status === "success") {
        successCount++;
        logAction("Create Clients", "Client", "", "", "", 
                  "Success", `Row ${r.row_index} - ${r.detail}`, 
                  "INFO");
      } else {
        failCount++;
        failMessages.push(`Row ${r.row_index} - ${r.detail}`);
        logAction("Create Clients", "Client", "", "", "", 
                  "Failed", `Row ${r.row_index} - ${r.detail}`, 
                  "ERROR");
      }
    });

    // Show summary
    const msg = `Clients Creation Summary:
    Total Rows Sent: ${resultObj.total_rows}
    Processed (Success): ${resultObj.processed_rows}
    Failures: ${failCount}
    ${failCount > 0 ? "Errors:\n" + failMessages.join("\n") : ""}`;

    SpreadsheetApp.getUi().alert(msg);

  } catch (error) {
    logError("addClientsSave", error, { validRows });
    SpreadsheetApp.getUi().alert("Error communicating with backend: " + error.message);
  }
}


function formatDate(dateStr) {
  if (!dateStr) return null;

  const parts = dateStr.split(' ');
  const [dayOfWeek, month, day, year] = parts;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthIndex = months.indexOf(month) + 1; // 1-based index
  return `${year}-${monthIndex.toString().padStart(2, '0')}-${day.padStart(2, '0')}`;
}


function updateClients() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    logAction(
      "Create Sheet",
      "Update Clients",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Update Clients' sheet",
      "INFO"
    );

    // Create or clear existing sheet
    let sheet = ss.getSheetByName("Update Clients");
    if (!sheet) {
      sheet = ss.insertSheet("Update Clients");
      logAction(
        "Create Sheet",
        "Update Clients",
        "",
        "",
        "",
        "Success",
        "Created new 'Update Clients' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Update Clients",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Update Clients' sheet",
        "INFO"
      );
    }

    // Header row with instructions
    sheet.getRange(1, 1, 1, 16)
      .merge()
      .setValue(
        "Instructions: Check rows to update. Editable fields: Broker Name, Broker Code, Distributor, Country Code, Phone, Email, Address, Account Start Date, Alias Fields.\n" +
        "Gray columns are read-only. Use dropdowns where available.\n" +
        "When done, click 'Save Changes' to send updates to the server."
      )
      .setBackground("#F4B084")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Define table headers
    const headers = [
      "Select",            // A
      "Client ID",         // B (read-only)
      "Client Name",       // C (read-only)
      "Broker Name",       // D
      "Broker Code",       // E
      "Distributor",       // F
      "PAN No.",           // G (read-only)
      "Country Code",      // H
      "Phone No.",         // I
      "Email ID",          // J
      "Address",           // K
      "Account Start Date",// L
      "Alias Name",        // M
      "Alias Phone No.",   // N
      "Alias Address",     // O
      "Type"               // P (read-only or editable as needed)
    ];
    sheet.getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#d67332")
      .setFontColor("#FFFFFF");

    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 140);

    // Add a checkbox column (Column A)
    const checkboxRange = sheet.getRange(3, 1, 1000);
    const checkboxRule = SpreadsheetApp.newDataValidation()
      .requireCheckbox()
      .build();
    checkboxRange.setDataValidation(checkboxRule);

    // Fetch client data from the backend
    let clientData = [];
    const endpoint = "http://15.207.59.232:8000/clients/list";

    try {
      const response = UrlFetchApp.fetch(endpoint);
      // Use handleApiResponse to log request/response if you like:
      //   handleApiResponse(response, "Fetch Clients");
      // But if you only want to parse, do so directly:
      clientData = JSON.parse(response.getContentText());

      logAction(
        "Fetch Data",
        "Clients",
        "",
        "",
        "",
        "Success",
        `Fetched ${clientData.length} clients from ${endpoint}`,
        "INFO"
      );
    } catch (error) {
      logError("updateClients:FetchClients", error);
      ui.alert("Error fetching client data: " + error.message);
    }

    // Populate sheet with client data
    if (clientData.length > 0) {
      // Map each client to its row
      const rowData = clientData.map(client => [
        false,                            // A (Select checkbox)
        client.client_id || "",           // B
        client.client_name || "",         // C
        client.broker_name || "",         // D
        client.broker_code || "",         // E
        client.distributor_name || "",    // F
        client.pan_no || "",             // G
        client.country_code || "",        // H
        client.phone_no || "",           // I
        client.email_id || "",           // J
        client.addr || "",               // K
        client.acc_start_date || "",      // L
        client.alias_name || "",          // M
        client.alias_phone_no || "",      // N
        client.alias_addr || "",          // O
        client.type || ""                 // P
      ]);
      sheet.getRange(3, 1, rowData.length, rowData[0].length).setValues(rowData);
    }

    /*
      PROTECT READ-ONLY COLUMNS
      Adjust as needed. The example sets B=2, C=3, G=7, and P=16 as read-only.
    */
    const readOnlyColumns = [2]; // B, C, G, P
    readOnlyColumns.forEach(colIdx => {
      const rangeToProtect = sheet.getRange(3, colIdx, sheet.getMaxRows() - 2);
      rangeToProtect.setBackground("#F3F3F3");

      const protection = rangeToProtect.protect();
      protection.setDescription(`Protected column ${colIdx} for read-only fields`);

      if (protection.canDomainEdit()) {
        protection.setDomainEdit(false);
      }

      const editors = protection.getEditors();
      if (editors && editors.length > 0) {
        protection.removeEditors(editors);
      }
    });

    let brokers = [];
    let distributors = [];
    try {
      brokers = getBrokersList();
      logAction("Fetch Data", "Brokers", "", "", "", "Success", `Fetched ${brokers.length} brokers`, "INFO");
    } catch (error) {
      logError("getBrokersList", error);
      ui.alert("Error fetching brokers: " + error.message);
    }

    try {
      distributors = getDistributorsList();
      logAction("Fetch Data", "Distributors", "", "", "", "Success", `Fetched ${distributors.length} distributors`, "INFO");
    } catch (error) {
      logError("getDistributorsList", error);
      ui.alert("Error fetching distributors: " + error.message);
    }

    // Apply Dropdowns for Brokers
    if (brokers.length > 0) {
      const brokerRange = sheet.getRange(3, 4, 1000);
      const brokerRule = SpreadsheetApp.newDataValidation()
        .requireValueInList(brokers, true)
        .setAllowInvalid(false)
        .build();
      brokerRange.setDataValidation(brokerRule);
    }

    // Apply Dropdowns for Distributors
    if (distributors.length > 0) {
      const distributorRange = sheet.getRange(3, 6, 1000);
      const distributorRule = SpreadsheetApp.newDataValidation()
        .requireValueInList(distributors, true)
        .setAllowInvalid(false)
        .build();
      distributorRange.setDataValidation(distributorRule);
    }

    ui.alert(
      "Update Client sheet ready",
      "Check rows to update, make changes, then click 'Save Changes' to send updates to the server.",
      ui.ButtonSet.OK
    );
    logAction(
      "Create Sheet",
      "Update Clients",
      "",
      "",
      "",
      "Completed",
      "'Update Clients' sheet successfully set up",
      "INFO"
    );
    sheet.activate();
  } catch (error) {
    logError("updateClients", error);
    ui.alert("Error creating or populating the 'Update Clients' sheet: " + error.message);
  }
}

function updateClientsSave() {

  function updatedFormatDate(date) {
    if (date instanceof Date && !isNaN(date)) {
      return Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd");
    } else {
      return "";
    }
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetName = "Update Clients";
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Sheet 'Update Clients' not found.");
    logAction(
      "Update Clients",
      "Sheet",
      "",
      "",
      "",
      "Failed",
      "No 'Update Clients' sheet found",
      "ERROR"
    );
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    ss.toast("No client rows found to update.", "Info", 3);
    return;
  }

  // Suppose columns are the same as your example,
  // but you have a checkbox in col A, and client_id in col B
  // We'll read 16 columns
  const dataRange = sheet.getRange(3, 1, lastRow - 2, 16);
  const data = dataRange.getValues();

  const updates = [];
  const noChangeMessages = [];

  // We'll do a simple approach: if row[0] == true, we attempt to update.
  // We skip advanced validations here, but you can add them if needed
  data.forEach((row, idx) => {
    if (row[0] === true) { // the checkbox in column A
      // Build a payload object

      let formattedDate = "";
      if (row[11]) {
        formattedDate = updatedFormatDate(row[11]); 
      }

      const updatePayload = {
        client_id: row[1],              // B
        client_name: row[2],           // C
        broker_name: row[3],           // D
        broker_code: row[4],           // E
        distributor_name: row[5],      // F
        pan_no: row[6],                // G
        country_code: row[7] ? String(row[7]) : "",
        phone_no: row[8] ? String(row[8]) : "",
        email_id: row[9],
        addr: row[10],
        acc_start_date: formattedDate,
        alias_name: row[12],
        alias_phone_no: row[13] ? String(row[13]) : "",
        alias_addr: row[14],
        type: row[15]
      };

      // You might remove empty fields if you only want partial updates
      // For example:
      // Object.entries(...).filter(([k,v]) => v !== "" && v !== null && v!==undefined)
      // ...
      // But we’ll keep it simple here

      // if client_id is missing, we’ll rely on backend partial logic
      updates.push(updatePayload);
    }
  });

  if (updates.length === 0) {
    ss.toast("No selected rows with changes found.", "Info", 3);
    return;
  }

  logAction(
    "Update Clients",
    "Sheet",
    "",
    "",
    "",
    "Sending",
    `Sending ${updates.length} updates to the server`,
    "INFO"
  );

  const url = "http://15.207.59.232:8000/clients/update";
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(updates),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    const contentText = response.getContentText();

    // Log raw response
    logAction(
      "Update Clients",
      "API Response",
      "",
      "",
      "",
      code === 200 ? "Success" : "Failed",
      `Response: ${contentText}`,
      code === 200 ? "INFO" : "ERROR"
    );

    if (code !== 200) {
      SpreadsheetApp.getUi().alert("Error updating clients: " + contentText);
      return;
    }

    // Partial success results
    const resultObj = JSON.parse(contentText);
    // { total_rows, processed_rows, results: [ {row_index, status, detail, client_id}, ... ] }

    let failCount = 0;
    let failMessages = [];
    let successCount = 0;

    resultObj.results.forEach(r => {
      if (r.status === "success") {
        successCount++;
        logAction("Update Clients", "Client", r.client_id, "", "", 
                  "Success", `Row ${r.row_index} - ${r.detail}`, "INFO");
      } else {
        failCount++;
        failMessages.push(`Row ${r.row_index} - ${r.detail}`);
        logAction("Update Clients", "Client", r.client_id, "", "", 
                  "Failed", `Row ${r.row_index} - ${r.detail}`, "ERROR");
      }
    });

    const msg = `Bulk Update Completed:
    Total Rows: ${resultObj.total_rows}
    Success: ${resultObj.processed_rows}
    Failures: ${failCount}
    ${failCount > 0 ? "Errors:\n" + failMessages.join("\n") : ""}`;

    SpreadsheetApp.getUi().alert(msg);

    ss.toast("Client updates applied. See logs for details.", "Success", 5);

  } catch (error) {
    logError("updateClientsSave", error, { updates });
    ss.toast("Client update failed: " + error.message, "Error", 5);
  }
}

function deleteClients() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    logAction(
      "Create Sheet",
      "Delete Clients",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Delete Clients' sheet",
      "INFO"
    );

    // Create or clear existing "Delete Clients" sheet
    let sheet = ss.getSheetByName("Delete Clients");
    if (!sheet) {
      sheet = ss.insertSheet("Delete Clients");
      logAction(
        "Create Sheet",
        "Delete Clients",
        "",
        "",
        "",
        "Success",
        "Created new 'Delete Clients' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Delete Clients",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Delete Clients' sheet",
        "INFO"
      );
    }

    // Row 1: Instructions (mirroring the 'Update Clients' design style)
    sheet
      .getRange(1, 1, 1, 8)
      .merge()
      .setValue(
        "Instructions: Check rows to delete. Gray columns are read-only. " +
        "When done, click 'Save Deletions' to remove these clients from the server."
      )
      .setBackground("#C06060")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Row 2: Column headers (only showing requested columns)
    const headers = [
      "Select",            // A
      "Client ID",         // B (read-only)
      "Client Name",       // C (read-only)
      "Broker Name",       // D
      "Broker Code",       // E
      "PAN No.",           // F (read-only)
      "Distributor",       // G
      "Account Start Date" // H
    ];
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#800000")
      .setFontColor("#FFFFFF");

    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 140);

    // Add a checkbox column (Column A)
    const checkboxRange = sheet.getRange(3, 1, 1000);
    const checkboxRule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
    checkboxRange.setDataValidation(checkboxRule);

    // Fetch client data from the backend
    let clientData = [];
    const endpoint = "http://15.207.59.232:8000/clients/list";
    try {
      const response = UrlFetchApp.fetch(endpoint);
      clientData = JSON.parse(response.getContentText());
      logAction(
        "Fetch Data",
        "Clients",
        "",
        "",
        "",
        "Success",
        `Fetched ${clientData.length} clients from ${endpoint}`,
        "INFO"
      );
    } catch (error) {
      logError("deleteClients:FetchClients", error);
      ui.alert("Error fetching client data: " + error.message);
    }

    // Populate sheet with requested columns
    if (clientData.length > 0) {
      const rowData = clientData.map((client) => [
        false,                             // A (Select checkbox)
        client.client_id || "",            // B
        client.client_name || "",          // C
        client.broker_name || "",          // D
        client.broker_code || "",          // E
        client.pan_no || "",               // F
        client.distributor_name || "",     // G
        client.acc_start_date || ""        // H
      ]);
      sheet.getRange(3, 1, rowData.length, headers.length).setValues(rowData);
    }

    /**
     * Protect read-only columns: 
     *   B=2 (Client ID), C=3 (Client Name), F=6 (PAN No.)
     * Adjust if you'd like to change which columns are locked.
     */
    const readOnlyCols = [2, 3, 6]; 
    readOnlyCols.forEach((colIdx) => {
      const rangeToProtect = sheet.getRange(3, colIdx, sheet.getMaxRows() - 2);
      rangeToProtect.setBackground("#F3F3F3");

      const protection = rangeToProtect.protect();
      protection.setDescription(`Protected column ${colIdx} for read-only fields`);

      if (protection.canDomainEdit()) {
        protection.setDomainEdit(false);
      }

      const editors = protection.getEditors();
      if (editors && editors.length > 0) {
        protection.removeEditors(editors);
      }
    });

    ui.alert(
      "Delete Clients sheet ready",
      "Check rows to delete, then click 'Save Deletions' to remove them from the server.",
      ui.ButtonSet.OK
    );
    logAction(
      "Create Sheet",
      "Delete Clients",
      "",
      "",
      "",
      "Completed",
      "'Delete Clients' sheet successfully set up",
      "INFO"
    );
    sheet.activate();
  } catch (error) {
    logError("deleteClients", error);
    ui.alert("Error creating or populating the 'Delete Clients' sheet: " + error.message);
  }
}

function deleteClientsSave() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetName = "Delete Clients";
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Sheet 'Delete Clients' not found.");
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    ss.toast("No clients in the sheet to check.", "Info", 3);
    return;
  }

  // Suppose we read 8 columns, with a checkbox in col A and client_id in col B
  const dataRange = sheet.getRange(3, 1, lastRow - 2, 8);
  const data = dataRange.getValues();

  // We'll build a simple array of client_ids
  const clientIdsToDelete = [];
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    if (row[0] === true) { // checkbox
      const cid = row[1] ? String(row[1]) : "";
      if (cid) clientIdsToDelete.push(cid);
    }
  }

  if (!clientIdsToDelete.length) {
    ss.toast("No clients selected for deletion.", "Info", 3);
    return;
  }

  // Confirm
  const ui = SpreadsheetApp.getUi();
  const confirmation = ui.alert(
    "Confirm Deletion",
    `Are you sure you want to delete ${clientIdsToDelete.length} client(s)? This action is irreversible.`,
    ui.ButtonSet.OK_CANCEL
  );
  if (confirmation !== ui.Button.OK) {
    ss.toast("Deletion canceled.", "Info", 3);
    return;
  }

  // Log the deletion request
  logAction(
    "Delete Clients",
    "Multiple",
    "",
    "",
    "",
    "Initiated",
    `Requested deletion of ${clientIdsToDelete.length} client(s).`,
    "INFO"
  );

  // Partial success endpoint
  const url = "http://15.207.59.232:8000/clients/delete";
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(clientIdsToDelete),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    const contentText = response.getContentText();

    logAction(
      "Delete Clients",
      "API Response",
      "",
      "",
      "",
      code === 200 ? "Success" : "Failed",
      `Response: ${contentText}`,
      code === 200 ? "INFO" : "ERROR"
    );

    if (code !== 200) {
      SpreadsheetApp.getUi().alert("Error deleting clients: " + contentText);
      return;
    }

    // Parse partial success
    const resultObj = JSON.parse(contentText);
    // { total_rows, processed_rows, results: [ {row_index, status, detail, client_id}, ... ] }

    let failCount = 0;
    let failMessages = [];
    let successCount = 0;

    resultObj.results.forEach(r => {
      if (r.status === "success") {
        successCount++;
        logAction("Delete Clients", "Client", r.client_id, "", "", 
                  "Success", `Row ${r.row_index} - ${r.detail}`, "INFO");
      } else {
        failCount++;
        failMessages.push(`Row ${r.row_index} - ${r.detail}`);
        logAction("Delete Clients", "Client", r.client_id, "", "", 
                  "Failed", `Row ${r.row_index} - ${r.detail}`, "ERROR");
      }
    });

    const msg = `Bulk Delete Completed:
    Total: ${resultObj.total_rows}
    Success: ${resultObj.processed_rows}
    Failures: ${failCount}
    ${failCount > 0 ? "Errors:\n" + failMessages.join("\n") : ""}`;

    SpreadsheetApp.getUi().alert(msg);
    ss.toast("Client deletion request processed. See logs for details.", "Success", 5);

  } catch (error) {
    logError("deleteClientsSave", error, { clientIdsToDelete });
    ss.toast("Client deletion failed: " + error.message, "Error", 5);
  }
}
