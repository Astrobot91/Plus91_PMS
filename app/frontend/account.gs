
function viewAccounts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    // Log the start of creating/clearing the read-only sheet
    logAction(
      "Create Sheet",
      "View Accounts",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Account Details' sheet",
      "INFO"
    );

    // 1) Create or clear the "Account Details" sheet
    const sheetName = "Account Details";
    let sheet = ss.getSheetByName(sheetName);

    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
      logAction(
        "Create Sheet",
        sheetName,
        "",
        "",
        "",
        "Success",
        `Created new '${sheetName}' sheet`,
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        sheetName,
        "",
        "",
        "",
        "Success",
        `Cleared existing '${sheetName}' sheet`,
        "INFO"
      );
    }

    // 2) Add a read-only notice at the top (merge columns as needed)
    const totalColumns = 13; // Because we have 13 columns below
    sheet
      .getRange(1, 1, 1, totalColumns)
      .merge()
      .setValue("Account Details Sheet: [Read Only]")
      .setBackground("#a4c2f4")
      .setFontColor("#000000")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    // 3) Create column headers in the second row
    const headers = [
      "Account ID",
      "Account Name",
      "Account Type",
      "Bracket Name",
      "Portfolio Name",
      "PF Value",
      "Cash Value",
      "Total Holdings",
      "Invested Amount",
      "Total TWRR",
      "Current Year TWRR",
      "CAGR",
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

    // 4) Fetch account data from the endpoint
    const endpoint = "http://15.207.59.232:8000/accounts/list";
    let accountData = [];

    try {
      logAction(
        "Fetch Data",
        "Accounts",
        "",
        "",
        "",
        "Started",
        "Fetching account data from " + endpoint,
        "INFO"
      );

      const response = UrlFetchApp.fetch(endpoint);
      const statusCode = response.getResponseCode();

      if (statusCode === 200) {
        const respObj = JSON.parse(response.getContentText());

        // If the response schema is { status: ..., data: [...] }:
        if (respObj && respObj.data) {
          accountData = respObj.data;
        }

        logAction(
          "Fetch Data",
          "Accounts",
          "",
          "",
          "",
          "Success",
          `Fetched ${accountData.length} accounts from ${endpoint}`,
          "INFO"
        );
      } else {
        logAction(
          "Fetch Data",
          "Accounts",
          "",
          "",
          "",
          "Failed",
          "Status code: " + statusCode,
          "ERROR"
        );
        ui.alert(`Failed to fetch account data. Status code: ${statusCode}`);
      }
    } catch (error) {
      logError("viewAccounts:FetchData", error);
      ui.alert("Error fetching account data: " + error.message);
    }

    // 5) Populate the sheet if we have data
    if (accountData.length > 0) {
      const rowData = accountData.map(acc => [
        acc.account_id || "",
        acc.account_name || "",
        acc.account_type || "",
        acc.bracket_name || "",
        acc.portfolio_name || "",
        acc.pf_value != null ? acc.pf_value : "",
        acc.cash_value != null ? acc.cash_value : "",
        acc.total_holdings != null ? acc.total_holdings : "",
        acc.invested_amt != null ? acc.invested_amt : "",
        acc.total_twrr != null ? acc.total_twrr : "",
        acc.current_yr_twrr != null ? acc.current_yr_twrr : "",
        acc.cagr != null ? acc.cagr : "",
        acc.created_at || ""
      ]);

      sheet
        .getRange(3, 1, rowData.length, headers.length)
        .setValues(rowData);

      logAction(
        "Populate Sheet",
        sheetName,
        "",
        "",
        "",
        "Success",
        `Populated ${rowData.length} rows with account data`,
        "INFO"
      );
    } else {
      logAction(
        "Populate Sheet",
        sheetName,
        "",
        "",
        "",
        "Success",
        "No account data found to display",
        "INFO"
      );
    }

    // 6) Color alternate rows (white for first row, #F8F8F8 for second, etc.)
    const startRow = 3; // first row of data
    const numRows = sheet.getLastRow() - (startRow - 1);
    for (let i = 0; i < numRows; i++) {
      const rowIndex = startRow + i;
      // even row index => #FFFFFF, odd => #F8F8F8
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
    try {
      const protectionRange = sheet.getRange(
        startRow,
        1,
        sheet.getMaxRows() - 2,
        headers.length
      );
      const protection = protectionRange.protect();
      protection.setDescription("Protected range for read-only sheet");

      if (protection.canDomainEdit()) {
        protection.setDomainEdit(false);
      }

      // Remove existing editors to ensure it's fully read-only
      const editors = protection.getEditors();
      if (editors && editors.length > 0) {
        protection.removeEditors(editors);
      }

      // Setting protections for the entire sheet generally might be needed:
      // sheet.protect().setWarningOnly(true);
    } catch (protError) {
      logAction(
        "Set Protection",
        sheetName,
        "",
        "",
        "",
        "Failed",
        "Unable to protect sheet range. " + protError.message,
        "ERROR"
      );
    }

    // Notify user that the sheet is ready
    ui.alert(
      "Account Details Sheet Ready",
      "This is a read-only sheet showing all accounts.",
      ui.ButtonSet.OK
    );

    logAction(
      "Create Sheet",
      "View Accounts",
      "",
      "",
      "",
      "Completed",
      `'${sheetName}' sheet successfully populated`,
      "INFO"
    );

    sheet.activate();
  } catch (error) {
    // Log and notify major errors
    logError("viewAccounts", error);
    ui.alert(
      `Error creating or populating the '${sheetName}' sheet: ${error.message}`
    );
  }
}

function updateAccounts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    logAction(
      "Create Sheet",
      "Update Accounts",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Update Accounts' sheet",
      "INFO"
    );

    // Create or clear the "Update Accounts" sheet
    let sheet = ss.getSheetByName("Update Accounts");
    if (!sheet) {
      sheet = ss.insertSheet("Update Accounts");
      logAction(
        "Create Sheet",
        "Update Accounts",
        "",
        "",
        "",
        "Success",
        "Created new 'Update Accounts' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Update Accounts",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Update Accounts' sheet",
        "INFO"
      );
    }

    // Provide instructions in row 1
    sheet.getRange(1, 1, 1, 12)
      .merge()
      .setValue(
        "Instructions:\n" +
        "1) Check rows to update (Column A)\n" +
        "2) Single accounts can edit PF Value, Cash Value, Invested Amt, and TWRR fields.\n" +
        "3) Joint accounts can only edit TWRR fields.\n" +
        "4) 'Total Holdings' and 'Created At' are read-only.\n" +
        "When done, click 'Save Account Changes'."
      )
      .setBackground("#F4B084")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Define columns
    const headers = [
      "Select",             // A
      "Account ID",         // B
      "Account Name",       // C (for reference)
      "Account Type",       // D (single/joint)
      "PF Value",           // E
      "Cash Value",         // F
      "Invested Amt",       // G
      "Total TWRR",         // H
      "Current Yr TWRR",    // I
      "CAGR",               // J
      "Total Holdings",     // K (read-only)
      "Created At"          // L (read-only)
    ];
    sheet.getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#d67332")
      .setFontColor("#FFFFFF");

    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 140);

    // Add checkboxes in column A
    const checkboxRange = sheet.getRange(3, 1, 1000);
    const checkboxRule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
    checkboxRange.setDataValidation(checkboxRule);

    // Fetch accounts from backend
    // e.g. GET /accounts/list => { status: "success", data: [ {account_id,...}, ... ] }
    // We'll parse 'data' property
    let accountData = [];
    try {
      const endpoint = "http://15.207.59.232:8000/accounts/list";
      const resp = UrlFetchApp.fetch(endpoint);
      const body = JSON.parse(resp.getContentText());
      accountData = body.data || [];
      logAction(
        "Fetch Data",
        "Accounts",
        "",
        "",
        "",
        "Success",
        `Fetched ${accountData.length} accounts`,
        "INFO"
      );
    } catch (err) {
      logError("updateAccounts:Fetch", err);
      ui.alert("Error fetching accounts: " + err.message);
    }

    // Populate
    if (accountData.length > 0) {
      const rowData = accountData.map(acc => [
        false, // checkbox
        acc.account_id || "",
        acc.account_name || "",
        acc.account_type || "",
        acc.pf_value != null ? acc.pf_value : "",
        acc.cash_value != null ? acc.cash_value : "",
        acc.invested_amt != null ? acc.invested_amt : "",
        acc.total_twrr != null ? acc.total_twrr : "",
        acc.current_yr_twrr != null ? acc.current_yr_twrr : "",
        acc.cagr != null ? acc.cagr : "",
        acc.total_holdings != null ? acc.total_holdings : "",
        acc.created_at || ""
      ]);
      sheet.getRange(3, 1, rowData.length, headers.length).setValues(rowData);
    }

    // Optionally protect columns K,L
    const readOnlyCols = [11, 12]; // col K=11, L=12
    readOnlyCols.forEach(col => {
      const rng = sheet.getRange(3, col, sheet.getMaxRows()-2);
      rng.setBackground("#F3F3F3");
      const prot = rng.protect().setDescription(`Protected col ${col} (TotalHoldings/CreatedAt)`);
      if (prot.canDomainEdit()) {
        prot.setDomainEdit(false);
      }
      const editors = prot.getEditors();
      if (editors && editors.length) {
        prot.removeEditors(editors);
      }
    });

    ui.alert(
      "Update Accounts Sheet Ready",
      "Select rows, edit fields for single/joint as allowed, then click 'Save Account Changes'.",
      ui.ButtonSet.OK
    );
    logAction(
      "Create Sheet",
      "Update Accounts",
      "",
      "",
      "",
      "Completed",
      "Sheet successfully populated",
      "INFO"
    );

    sheet.activate();
  } catch (err) {
    logError("updateAccounts", err);
    ui.alert("Error creating or populating 'Update Accounts' sheet: " + err.message);
  }
}

function updateAccountsSave() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetName = "Update Accounts";
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Sheet 'Update Accounts' not found.");
    logAction("Update Accounts", "Sheet", "", "", "", "Failed", "Sheet not found", "ERROR");
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    ss.toast("No accounts found to update.", "Info", 3);
    return;
  }

  // We have 12 columns
  // A: checkbox
  // B: account_id
  // C: account_name (not used for update, only reference)
  // D: account_type
  // E: pf_value
  // F: cash_value
  // G: invested_amt
  // H: total_twrr
  // I: current_yr_twrr
  // J: cagr
  // K: total_holdings (read-only)
  // L: created_at (read-only)
  const numCols = 12;
  const dataRange = sheet.getRange(3, 1, lastRow - 2, numCols);
  const data = dataRange.getValues();

  const updates = [];

  data.forEach((row, idx) => {
    if (row[0] === true) {
      // parse row
      const accountId = row[1] ? row[1].toString().trim() : "";
      const accountName = row[2] || "";
      const accountType = row[3] ? row[3].toString().trim() : "";

      // parse numbers carefully
      const pfVal = row[4] !== "" ? parseFloat(row[4]) : undefined;
      const cashVal = row[5] !== "" ? parseFloat(row[5]) : undefined;
      const investedAmt = row[6] !== "" ? parseFloat(row[6]) : undefined;
      const totalTwrr = row[7] !== "" ? parseFloat(row[7]) : undefined;
      const currentYrTwrr = row[8] !== "" ? parseFloat(row[8]) : undefined;
      const cagr = row[9] !== "" ? parseFloat(row[9]) : undefined;

      const updatePayload = {
        account_id: accountId,
        account_type: accountType
      };

      if (!isNaN(pfVal)) updatePayload.pf_value = pfVal;
      if (!isNaN(cashVal)) updatePayload.cash_value = cashVal;
      if (!isNaN(investedAmt)) updatePayload.invested_amt = investedAmt;
      if (!isNaN(totalTwrr)) updatePayload.total_twrr = totalTwrr;
      if (!isNaN(currentYrTwrr)) updatePayload.current_yr_twrr = currentYrTwrr;
      if (!isNaN(cagr)) updatePayload.cagr = cagr;

      updates.push(updatePayload);

      logAction(
        "Validation",
        "Account",
        accountName,
        "",
        "",
        "Pending",
        `Row ${idx+3}: Updating ${accountType} => ID: ${accountId}`,
        "INFO"
      );
    }
  });

  if (updates.length === 0) {
    ss.toast("No rows selected for update.", "Info", 3);
    return;
  }

  logAction("Update Accounts", "Sheet", "", "", "", "Sending", 
            `Sending ${updates.length} account updates`, "INFO");

  // Call partial-success endpoint /accounts/update
  const url = "http://15.207.59.232:8000/accounts/update";
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(updates),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    const text = response.getContentText();

    logAction(
      "Update Accounts",
      "API Response",
      "",
      "",
      "",
      code === 200 ? "Success" : "Failed",
      `Response: ${text}`,
      code === 200 ? "INFO" : "ERROR"
    );

    if (code !== 200) {
      SpreadsheetApp.getUi().alert(`Error updating accounts: ${text}`);
      return;
    }

    const result = JSON.parse(text); 
    // result => { total_rows, processed_rows, results: [ {row_index, status, detail, account_id}, ... ] }

    let failCount = 0;
    let successCount = 0;
    let failMsgs = [];

    result.results.forEach(r => {
      if (r.status === "success") {
        successCount++;
        logAction("Update Accounts", "Account", r.account_id, "", "", 
                  "Success", `Row ${r.row_index}: ${r.detail}`, "INFO");
      } else {
        failCount++;
        failMsgs.push(`Row ${r.row_index}: ${r.detail}`);
        logAction("Update Accounts", "Account", r.account_id, "", "", 
                  "Failed", `Row ${r.row_index}: ${r.detail}`, "ERROR");
      }
    });

    const msg = `Bulk Update Completed:
      Total Rows: ${result.total_rows}
      Success: ${result.processed_rows}
      Failures: ${failCount}
      ${failCount > 0 ? "Errors:\n" + failMsgs.join("\n") : ""}`;

    SpreadsheetApp.getUi().alert(msg);
    ss.toast("Account updates completed. Check Logs for details.", "Success", 5);

  } catch (err) {
    logError("updateAccountsSave", err, { updates });
    ss.toast("Account update failed: " + err.message, "Error", 5);
  }
}


function manageJointAccounts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    // Log the beginning of the sheet setup
    logAction(
      "Create Sheet",
      "Manage Joint Accounts",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Manage Joint Accounts' sheet",
      "INFO"
    );

    // Create or clear the 'Manage Joint Accounts' sheet
    let sheet = ss.getSheetByName("Manage Joint Accounts");
    if (!sheet) {
      sheet = ss.insertSheet("Manage Joint Accounts");
      logAction(
        "Create Sheet",
        "Manage Joint Accounts",
        "",
        "",
        "",
        "Success",
        "Created new 'Manage Joint Accounts' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Manage Joint Accounts",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Manage Joint Accounts' sheet",
        "INFO"
      );
    }

    // Add a header cell with instructions
    sheet
      .getRange(1, 1, 1, 5)
      .merge()
      .setValue(
        "Instructions:\n" +
        "1. Specify the action (create, update, or delete) in the dropdown.\n" +
        "2. When updating or deleting, include a valid Joint Account ID. If creating, leave ID blank.\n" +
        "3. 'Linked Single Accounts' should be comma-separated IDs.\n" +
        "4. After filling in rows, click 'Save Joint Accounts' to send changes to the server."
      )
      .setBackground("#F4B084")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Define table headers
    const headers = [
      "Action",                 // Column A
      "Joint Account ID",       // Column B
      "Account Name",           // Column C
      "Linked Single Accounts", // Column D
      "Status/Notes"            // Column E
    ];
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#000000")
      .setFontColor("#ffffff");

    // Freeze the header row
    sheet.setFrozenRows(2);

    // Adjust column widths
    sheet.setColumnWidths(1, headers.length, 220);

    // Create a dropdown in column A (Action) for 100 rows, allowing only "create", "update", or "delete"
    const actionRange = sheet.getRange(3, 1, 100); // from row 3 to row 102, column A
    const actionRule = SpreadsheetApp.newDataValidation()
      .requireValueInList(["create", "update", "delete"], true)
      .setAllowInvalid(false)
      .build();
    actionRange.setDataValidation(actionRule);

    // Log that the sheet setup is complete
    logAction(
      "Create Sheet",
      "Manage Joint Accounts",
      "",
      "",
      "",
      "Completed",
      "'Manage Joint Accounts' sheet successfully set up",
      "INFO"
    );

    // Bring the sheet into focus
    sheet.activate();
  } catch (error) {
    // Log errors and notify the user
    logError("manageJointAccounts", error);
    ui.alert(
      "Error creating or populating the 'Manage Joint Accounts' sheet: " + error.message
    );
  }
}

function saveJointAccountChanges() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName("Manage Joint Accounts");
  if (!sheet) {
    ui.alert("Sheet 'Manage Joint Accounts' not found.");
    logAction(
      "Save Changes",
      "Manage Joint Accounts",
      "",
      "",
      "",
      "Failed",
      "No 'Manage Joint Accounts' sheet found",
      "ERROR"
    );
    return;
  }

  // Determine how many rows have data
  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    // No data rows after header row (which ends at row 2)
    ui.alert("No rows found to process.");
    return;
  }

  // Read data starting from row 3 (row 1: instructions, row 2: headers)
  const dataRange = sheet.getRange(3, 1, lastRow - 2, 5);
  const data = dataRange.getValues();

  // Will keep track of how many total actions we attempt
  let totalActions = 0;
  // We'll store any error messages in an array to present to the user
  const errors = [];

  // Iterate over each row, sending the appropriate request
  data.forEach((row, idx) => {
    const action = (row[0] || "").toString().trim().toLowerCase();
    const jointAccountId = (row[1] || "").toString().trim();
    const accountName = (row[2] || "").toString().trim();
    const linkedAccountsRaw = (row[3] || "").toString().trim();

    // Skip empty rows (no action)
    if (!action) {
      return;
    }

    // Parse comma-separated single accounts into an array
    let linkedSingleAccounts = [];
    if (linkedAccountsRaw) {
      linkedSingleAccounts = linkedAccountsRaw
        .split(",")
        .map(item => item.trim())
        .filter(item => !!item);
    }

    // We use different endpoints based on the action
    let url = "";
    let method = "";
    let payloadObj = {};

    if (action === "create") {
      // POST /joint-accounts
      url = "http://15.207.59.232:8000/joint-accounts";
      method = "post";
      payloadObj = {
        joint_account_name: accountName,
        single_account_ids: linkedSingleAccounts
      };
    } else if (action === "update") {
      // PUT /joint-accounts/{joint_account_id}
      if (!jointAccountId) {
        errors.push(
          `Row ${idx + 3}: 'update' requires a valid Joint Account ID. Skipping.`
        );
        return;
      }
      url = `http://15.207.59.232:8000/joint-accounts/${jointAccountId}`;
      method = "put";
      payloadObj = {
        joint_account_name: accountName,
        single_account_ids: linkedSingleAccounts
      };
    } else if (action === "delete") {
      // DELETE /joint-accounts/{joint_account_id}
      if (!jointAccountId) {
        errors.push(
          `Row ${idx + 3}: 'delete' requires a valid Joint Account ID. Skipping.`
        );
        return;
      }
      url = `http://15.207.59.232:8000/joint-accounts/${jointAccountId}`;
      method = "delete";
      // Usually, delete requests can be empty or minimal
      // but if the backend expects a body, add it here
    } else {
      // Unrecognized action
      errors.push(`Row ${idx + 3}: Unknown action '${action}'. Skipping.`);
      return;
    }

    // We'll proceed if we have a valid method
    const options = {
      method: method,
      contentType: "application/json",
      muteHttpExceptions: true
    };

    // DELETE typically doesn't need a payload. If it's needed, uncomment:
    if (method !== "delete") {
      options.payload = JSON.stringify(payloadObj);
    }

    // Attempt the request
    try {
      const response = UrlFetchApp.fetch(url, options);
      const code = response.getResponseCode();
      const text = response.getContentText();

      totalActions += 1;
      if (code >= 200 && code < 300) {
        logAction(
          method.toUpperCase(),
          "Manage Joint Accounts",
          jointAccountId,
          accountName,
          linkedAccountsRaw,
          "Success",
          `Server responded with: ${text}`,
          "INFO"
        );
      } else {
        // Log error
        const msg = `Failed Action: ${action.toUpperCase()}, Row ${idx + 3} => Code: ${code}, Response: ${text}`;
        logAction(
          method.toUpperCase(),
          "Manage Joint Accounts",
          jointAccountId,
          accountName,
          linkedAccountsRaw,
          "Failed",
          msg,
          "ERROR"
        );
        errors.push(msg);
      }
    } catch (error) {
      const msg = `Error in sending '${action.toUpperCase()}' for Row ${
        idx + 3
      }: ${error.toString()}`;
      logError("saveJointAccountChanges", error);
      errors.push(msg);
    }
  });

  // Summarize the results to the user
  logAction(
    "Save Changes",
    "Manage Joint Accounts",
    "",
    "",
    "",
    "Completed",
    `Completed ${totalActions} actions with ${errors.length} errors`,
    "INFO"
  );

  if (errors.length > 0) {
    ui.alert(
      `Finished processing with errors:\n\n${errors.join("\n")}`
    );
  } else if (totalActions > 0) {
    ui.alert(`Successfully processed ${totalActions} joint account actions!`);
  } else {
    // No actions processed
    ui.alert("No actions were processed.");
  }
}
