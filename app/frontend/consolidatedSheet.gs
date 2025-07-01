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

    // First check if all required sheets exist
    const accountSheet = ss.getSheetByName("Account Details");
    const clientSheet = ss.getSheetByName("Client Details");
    const basketAllocSheet = ss.getSheetByName("Basket % Allocations");

    if (!accountSheet) {
      ui.alert("Error: 'Account Details' sheet not found. Please run viewAccounts first.");
      return;
    }

    if (!clientSheet) {
      ui.alert("Error: 'Client Details' sheet not found. Please run viewClients first.");
      return;
    }

    if (!basketAllocSheet) {
      ui.alert("Error: 'Basket % Allocations' sheet not found. Please run viewBasketAllocations first.");
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

    // Get ALL DATA from the basket allocations sheet including headers
    const basketAllocFullData = basketAllocSheet.getDataRange().getValues();

    // Extract headers (row 2) and data (row 3 onwards)
    const basketAllocHeaders = basketAllocFullData[1]; // Assuming headers are on row 2
    const basketAllocData = basketAllocFullData.slice(2); // Data starts from row 3

    // Find column indices for important fields in Basket % Allocations
    const basketAllocColumns = {
      accountId: 1, // Assuming Account ID is the first column (index 0)
      brokerName: -1,
      brokerCode: -1
    };

    // Log the headers to debug column structure
    logAction("Headers", "Basket % Allocations", "", "", "", "Info",
             `Headers: ${JSON.stringify(basketAllocHeaders)}`, "INFO");

    // Search for broker name and code columns in the headers
    for (let i = 0; i < basketAllocHeaders.length; i++) {
      const header = basketAllocHeaders[i] ? basketAllocHeaders[i].toString().toLowerCase() : "";

      if (header.includes("broker") && header.includes("name")) {
        basketAllocColumns.brokerName = i;
        logAction("Column Found", "Broker Name (Basket)", "", "", "", "Info",
                 `Found at index ${i}: ${basketAllocHeaders[i]}`, "INFO");
      }

      if (header.includes("broker") && header.includes("code")) {
        basketAllocColumns.brokerCode = i;
        logAction("Column Found", "Broker Code (Basket)", "", "", "", "Info",
                 `Found at index ${i}: ${basketAllocHeaders[i]}`, "INFO");
      }
    }

    // If we couldn't find the columns by name, log a warning and use fallbacks
    if (basketAllocColumns.brokerName === -1 || basketAllocColumns.brokerCode === -1) {
      logAction("Warning", "Column Detection (Basket)", "", "", "", "Failed",
               `Could not auto-detect broker columns. brokerName=${basketAllocColumns.brokerName}, brokerCode=${basketAllocColumns.brokerCode}`, "WARN");

      // Log the first few rows to help debugging
      for (let i = 0; i < Math.min(3, basketAllocData.length); i++) {
        logAction("Data Sample (Basket)", `Row ${i+3}`, "", "", "", "Info",
                 `${JSON.stringify(basketAllocData[i])}`, "INFO");
      }

      // As a fallback, try these positions (adjust as needed based on your sheet structure)
      // These are just examples, update them if your sheet structure is different
      if (basketAllocColumns.brokerName === -1) basketAllocColumns.brokerName = 5; // Example: Column F
      if (basketAllocColumns.brokerCode === -1) basketAllocColumns.brokerCode = 6; // Example: Column G
      logAction("Fallback", "Column Detection (Basket)", "", "", "", "Using Fallbacks",
               `Using fallback indices: brokerName=${basketAllocColumns.brokerName}, brokerCode=${basketAllocColumns.brokerCode}`, "INFO");
    }


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

    // Create a map of broker codes for joint accounts from basket allocations
    const jointAccountBrokerMap = {};
    let jointAccountsFound = 0;

    // Process basket allocation data for joint accounts
    basketAllocData.forEach((row, index) => {
      const accountId = row[basketAllocColumns.accountId]; // Use determined accountId column index

      // Only process joint accounts
      if (accountId && accountId.toString().startsWith('JACC')) {
        const brokerName = basketAllocColumns.brokerName >= 0 ? row[basketAllocColumns.brokerName] : "";
        const brokerCode = basketAllocColumns.brokerCode >= 0 ? row[basketAllocColumns.brokerCode] : "";

        logAction("Joint Account Row (Basket)", `${accountId}`, "", "", "", "Data",
                 `Row ${index+3}: ${JSON.stringify(row)}`, "INFO");
        logAction("Joint Account (Basket)", `${accountId}`, "", "", "", "Columns",
                 `Using brokerName col ${basketAllocColumns.brokerName}, brokerCode col ${basketAllocColumns.brokerCode}`, "INFO");
        logAction("Joint Account (Basket)", `${accountId}`, "", "", "", "Values",
                 `Found brokerName='${brokerName}', brokerCode='${brokerCode}'`, "INFO");

        if (brokerName || brokerCode) {
          jointAccountBrokerMap[accountId] = {
            brokerName: brokerName || "",
            brokerCode: brokerCode || ""
          };
          jointAccountsFound++;
        }
      }
    });

    logAction("Joint Accounts (Basket)", "Scan", "", "", "", "Completed",
             `Found ${jointAccountsFound} joint accounts with broker information from Basket Allocations`, "INFO");


    // Prepare the consolidated data
    const consolidatedData = [];

    // Process accounts (both single and joint)
    Object.keys(accountMap).forEach(accountId => {
      const account = accountMap[accountId];
      const client = clientMap[accountId] || {}; // For joint accounts, this might be empty

      // Default values (will be used for single accounts)
      let brokerName = client.brokerName || "";
      let brokerCode = client.brokerCode || "";
      let phoneNo = client.phoneNo || "";
      let emailId = client.emailId || "";
      let address = client.address || "";
      let accountStartDate = client.accountStartDate || "";
      let distributor = client.distributor || "";

      // For joint accounts (IDs starting with JACC), use the specific logic to fetch details
      if (accountId.toString().startsWith('JACC')) {
        logAction("Joint Account", accountId, "", "", "", "Processing",
                 "Looking up broker info in jointAccountBrokerMap", "INFO");

        const jointBrokerInfo = jointAccountBrokerMap[accountId] || {};
        brokerName = jointBrokerInfo.brokerName || brokerName; // Prefer basket info, fallback to clientMap if any
        brokerCode = jointBrokerInfo.brokerCode || brokerCode;

        logAction("Joint Account", accountId, "", "", "", "Info",
                 `Using broker info: Name='${brokerName}', Code='${brokerCode}'`, "INFO");

        if (brokerCode) {
          let brokerCodes = [];
          const codeStr = brokerCode.toString();

          if (codeStr.includes(' - ')) {
            brokerCodes = codeStr.split(' - ').map(code => code.trim()).filter(c => c);
          } else if (codeStr.includes('-')) {
            brokerCodes = codeStr.split('-').map(code => code.trim()).filter(c => c);
          } else if (codeStr.includes(',')) {
            brokerCodes = codeStr.split(',').map(code => code.trim()).filter(c => c);
          } else if (codeStr.includes(';')) {
            brokerCodes = codeStr.split(';').map(code => code.trim()).filter(c => c);
          } else if (codeStr.includes(' ')) { // Split by space as a general fallback
            brokerCodes = codeStr.split(' ').map(code => code.trim()).filter(c => c);
          } else {
            brokerCodes = [codeStr.trim()].filter(c => c);
          }

          logAction("Joint Account", accountId, "", "", "", "Codes",
                   `Split broker code into ${brokerCodes.length} codes: ${brokerCodes.join(", ")}`, "INFO");

          const linkedSingleAccounts = [];
          Object.values(clientMap).forEach(clientInfo => {
            if (clientInfo.accountId && clientInfo.accountId.toString().startsWith('JACC')) {
              return; // Skip other joint accounts
            }
            if (clientInfo.brokerCode) {
              const clientBrokerCodeStr = clientInfo.brokerCode.toString();
              if (brokerCodes.includes(clientBrokerCodeStr)) {
                logAction("Joint Account", accountId, "", "", "", "Match",
                         `Found exact match with single account ${clientInfo.accountId}, broker code ${clientBrokerCodeStr}`, "INFO");
                linkedSingleAccounts.push(clientInfo);
              } else {
                for (const code of brokerCodes) {
                  if (code && (clientBrokerCodeStr.includes(code) || code.includes(clientBrokerCodeStr))) {
                    logAction("Joint Account", accountId, "", "", "", "Match",
                             `Found partial match with single account ${clientInfo.accountId}, broker code ${clientBrokerCodeStr} ~ ${code}`, "INFO");
                    linkedSingleAccounts.push(clientInfo);
                    break; 
                  }
                }
              }
            }
          });

          logAction("Joint Account", accountId, "", "", "", "Linked",
                   `Found ${linkedSingleAccounts.length} linked single accounts`, "INFO");

          let oldestDate = null;
          linkedSingleAccounts.forEach(linkedAccount => {
            if (!phoneNo && linkedAccount.phoneNo) phoneNo = linkedAccount.phoneNo;
            if (!emailId && linkedAccount.emailId) emailId = linkedAccount.emailId;
            if (!address && linkedAccount.address) address = linkedAccount.address;
            if (!distributor && linkedAccount.distributor) distributor = linkedAccount.distributor;

            const startDate = linkedAccount.accountStartDate;
            if (startDate) {
              try {
                const dateObj = new Date(startDate);
                if (!isNaN(dateObj.getTime())) { // Check if it's a valid date
                  if (!oldestDate || dateObj < oldestDate) {
                    oldestDate = dateObj;
                  }
                }
              } catch(e) { /* ignore invalid date formats */ }
            }
          });
          if (oldestDate) {
            accountStartDate = Utilities.formatDate(oldestDate, ss.getSpreadsheetTimeZone(), "yyyy-MM-dd");
             logAction("Joint Account", accountId, "", "", "", "Set",
                       `Set account start date to ${accountStartDate}`, "INFO");
          }
        }
      }

      const row = [
        client.clientId || "",
        accountId,
        account.accountName || client.clientName || "", // Use account name, fallback to client name
        brokerName,
        brokerCode,
        client.brokerPassword || "", // Only for single accounts from clientMap
        client.panNo || "",
        client.countryCode || "",
        phoneNo,
        emailId,
        address,
        accountStartDate ? (typeof accountStartDate === 'string' ? accountStartDate : Utilities.formatDate(new Date(accountStartDate), ss.getSpreadsheetTimeZone(), "yyyy-MM-dd")) : "",
        distributor,
        account.accountType || "",
        account.bracketName || "",
        account.portfolioName || "",
        account.pfValue || "",
        account.cashValue || "",
        account.totalHoldings || "",
        account.investedAmount || "",
        account.totalTwrr || "",
        account.currentYearTwrr || "",
        account.cagr || "",
        account.lastUpdated ? (typeof account.lastUpdated === 'string' ? account.lastUpdated : Utilities.formatDate(new Date(account.lastUpdated), ss.getSpreadsheetTimeZone(), "yyyy-MM-dd HH:mm:ss")) : ""
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

      // Color alternate rows and highlight rows with blank/zero "Total Holdings"
      const startRow = 3;
      const numRows = consolidatedData.length;
      const totalHoldingsColumnIndex = headers.indexOf("Total Holdings"); // Should be 18

      for (let i = 0; i < numRows; i++) {
        const rowIndex = startRow + i;
        const currentRowRange = sheet.getRange(rowIndex, 1, 1, headers.length);
        const totalHoldingsValue = consolidatedData[i][totalHoldingsColumnIndex];

        // Default alternate row coloring
        if (i % 2 === 0) {
          currentRowRange.setBackground("#FFFFFF"); // White
        } else {
          currentRowRange.setBackground("#F8F8F8"); // Light Gray
        }

        // Highlight if Total Holdings is blank or 0
        if (!totalHoldingsValue || parseFloat(totalHoldingsValue) === 0) {
          currentRowRange.setBackground("#FFEB9C"); // Yellow
        }
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
