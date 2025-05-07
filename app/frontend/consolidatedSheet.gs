function createConsolidatedSheet() {

  viewAccounts()
  viewClients()
  viewBasketAllocations()
  openStandardPortfolioSheet()

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    // Log the start of creating/clearing the consolidated sheet
    logAction(
      "Create Sheet",
      "Consolidated View",
      "",
      "",
      "",
      "Started",
      "Attempting to create or clear the 'Consolidated Sheet'",
      "INFO"
    );

    // First check if both required sheets exist
    const accountSheet = ss.getSheetByName("Account Details");
    const clientSheet = ss.getSheetByName("Client Details");

    if (!accountSheet) {
      ui.alert("Error: 'Account Details' sheet not found. Please run viewAccounts first.");
      return;
    }

    if (!clientSheet) {
      ui.alert("Error: 'Client Details' sheet not found. Please run viewClients first.");
      return;
    }

    // Create or clear the "Consolidated Sheet"
    const sheetName = "Consolidated Sheet";
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
        `Created new '${sheetName}'`,
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
        `Cleared existing '${sheetName}'`,
        "INFO"
      );
    }

    // Define the column headers for the consolidated sheet
    const headers = [
      "Client ID",
      "Account ID",
      "Client Name",
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
      "Last Updated"
    ];

    const totalColumns = headers.length;

    // Add a read-only notice at the top
    sheet
      .getRange(1, 1, 1, totalColumns)
      .merge()
      .setValue("Consolidated Sheet [Read Only]")
      .setBackground("#a4c2f4")
      .setFontColor("#000000")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    // Add the headers in the second row
    sheet
      .getRange(2, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight("bold")
      .setBackground("#3c78d8")
      .setFontColor("#FFFFFF");

    sheet.setFrozenRows(2);
    sheet.setColumnWidths(1, headers.length, 130);

    // Get data from the account sheet (starting from row 3, which is after headers)
    const accountLastRow = accountSheet.getLastRow();
    const accountData = accountLastRow > 2 
      ? accountSheet.getRange(3, 1, accountLastRow - 2, 14).getValues() 
      : [];

    // Get data from the client sheet (starting from row 3, which is after headers)
    const clientLastRow = clientSheet.getLastRow();
    const clientData = clientLastRow > 2 
      ? clientSheet.getRange(3, 1, clientLastRow - 2, 19).getValues() 
      : [];

    // Create a map of account data for quick lookup
    const accountMap = {};
    accountData.forEach(row => {
      const accountId = row[0]; // Account ID is in the first column
      if (accountId) {
        accountMap[accountId] = {
          accountId: row[0],
          accountName: row[1],
          accountType: row[2],
          bracketName: row[3],
          portfolioName: row[4],
          pfValue: row[5],
          cashValue: row[6],
          totalHoldings: row[7],
          investedAmount: row[8],
          totalTwrr: row[9],
          currentYearTwrr: row[10],
          cagr: row[11],
          lastUpdated: row[12]
        };
      }
    });

    // Create a map of client data for quick lookup
    const clientMap = {};
    clientData.forEach(row => {
      const accountId = row[2]; // Account ID is in the third column for clients
      if (accountId) {
        clientMap[accountId] = {
          clientId: row[0],
          clientName: row[1],
          accountId: row[2],
          brokerName: row[3],
          brokerCode: row[4],
          brokerPassword: row[5],
          panNo: row[6],
          countryCode: row[7],
          phoneNo: row[8],
          emailId: row[9],
          address: row[10],
          accountStartDate: row[11],
          distributor: row[12],
          onboardStatus: row[13],
          type: row[14],
          aliasName: row[15],
          aliasPhoneNo: row[16],
          aliasAddr: row[17],
          createdAt: row[18]
        };
      }
    });

    // Prepare the consolidated data
    // First, add all accounts with client data (single accounts)
    const consolidatedData = [];
    
    // Process accounts (both single and joint)
    Object.keys(accountMap).forEach(accountId => {
      const account = accountMap[accountId];
      const client = clientMap[accountId] || {}; // For joint accounts, this might be empty
      
      const row = [
        client.clientId || "", // Client ID
        accountId, // Account ID
        account.accountName || "", // Client Name - from Account Name
        client.brokerName || "", // Broker Name
        client.brokerCode || "", // Broker Code
        client.brokerPassword || "", // Broker Password
        client.panNo || "", // PAN No.
        client.countryCode || "", // Country Code
        client.phoneNo || "", // Phone No.
        client.emailId || "", // Email ID
        client.address || "", // Address
        client.accountStartDate || "", // Account Start Date
        client.distributor || "", // Distributor
        account.accountType || "", // Account Type
        account.bracketName || "", // Bracket Name
        account.portfolioName || "", // Portfolio Name
        account.pfValue || "", // PF Value
        account.cashValue || "", // Cash Value
        account.totalHoldings || "", // Total Holdings
        account.investedAmount || "", // Invested Amount
        account.totalTwrr || "", // Total TWRR
        account.currentYearTwrr || "", // Current Year TWRR
        account.cagr || "", // CAGR
        account.lastUpdated || "" // Last Updated
      ];
      
      consolidatedData.push(row);
    });

    // Sort by account ID for better readability
    consolidatedData.sort((a, b) => {
      const accountIdA = a[1] || "";
      const accountIdB = b[1] || "";
      return accountIdA.localeCompare(accountIdB);
    });

    // Write the consolidated data to the sheet
    if (consolidatedData.length > 0) {
      sheet.getRange(3, 1, consolidatedData.length, headers.length).setValues(consolidatedData);
      
      // Color alternate rows
      const startRow = 3;
      const numRows = consolidatedData.length;
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
      
      // Make the sheet read-only by protecting it
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
    }

    // Log completion and notify user
    logAction(
      "Create Sheet",
      "Consolidated View",
      "",
      "",
      "",
      "Completed",
      `Created consolidated sheet with ${consolidatedData.length} rows`,
      "INFO"
    );

    ui.alert(
      "Consolidated Sheet Ready",
      `Successfully created consolidated view with ${consolidatedData.length} accounts.`,
      ui.ButtonSet.OK
    );

    // Activate the sheet
    sheet.activate();

  } catch (error) {
    // Log and notify any errors
    logError("createConsolidatedSheet", error);
    ui.alert(
      "Error creating consolidated sheet: " + error.message
    );
  }
}