// CREATE MENU
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu("Account Operations")
    .addSubMenu(
      ui.createMenu("Manage Clients & Accounts")
        .addItem("View Clients", "viewClients")
        .addItem("Add Clients", "addClients")
        .addItem("Update Clients", "updateClients")
        .addItem("Delete Clients", "deleteClients")
        .addItem("View Accounts", "viewAccounts")
        .addItem("Update Accounts", "updateAccounts")
        .addItem("Manage Joint Accounts", "manageJointAccounts")
        .addItem("Save", "saveClientChanges")
    )
    .addSubMenu(
      ui.createMenu("Manage Portfolio Structure")
        .addItem("Standard Portfolio", "openStandardPortfolioSheet")
        .addItem("Save", "savePortfolioChanges")
    )
    .addSubMenu(
      ui.createMenu("Manage Manual Inputs")
        .addItem("Input Actual Portfolios", "setupActualPortfolioSheet")
        .addItem("Input Cashflows", "setupCashflowsSheet")
        .addItem("Stock Exceptions", "setupExceptionsSheet")
    )
    .addItem("Manage Brokers & Distributors", "showManagementSidebar")
    .addToUi();

  // Setup log cleanup if it doesn't exist
  const triggers = ScriptApp.getProjectTriggers();
  const hasCleanupTrigger = triggers.some(trigger => 
    trigger.getHandlerFunction() === 'cleanupLogs'
  );
  
  if (!hasCleanupTrigger) {
    createLogCleanupTrigger();
  }
  
  // Clean up logs on open if they're too large
  cleanupLogs();

  viewClients();
  viewAccounts();

}

function saveClientChanges() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const addSheet = ss.getSheetByName("Add Clients");
  if (addSheet) {
    addClientsSave();
    ss.deleteSheet(addSheet);
  }

  const updateSheet = ss.getSheetByName("Update Clients");
  if (updateSheet) {
    updateClientsSave();
    ss.deleteSheet(updateSheet);
  }

  // Check if "Delete Clients" sheet exists:
  const deleteSheet = ss.getSheetByName("Delete Clients");
  if (deleteSheet) {
    deleteClientsSave();
    ss.deleteSheet(deleteSheet);
  }

  // Check if "Update Account" sheet exists:
  const updateAccountSheet = ss.getSheetByName("Update Accounts");
  if (updateAccountSheet) {
    updateAccountsSave();
    ss.deleteSheet(updateAccountSheet);
  }

  // Check if "Manage Joint Accounts" sheet exists:
  const jointAccountSheet = ss.getSheetByName("Manage Joint Accounts");
  if (jointAccountSheet) {
    saveJointAccountChanges();
    ss.deleteSheet(jointAccountSheet);
  }

  viewClients();
  viewAccounts();
}

function saveManualInputs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const actualPortfolioSheet = ss.getSheetByName("Actual Portfolio Input")
  if (actualPortfolioSheet) {
    saveActualPortfolio();
    ss.deleteSheet(actualPortfolioSheet);
  }

  const exceptionsSheet = ss.getSheetByName("Exceptions")
  if (exceptionsSheet) {
    saveExceptions();
    ss.deleteSheet(exceptionsSheet);
  }

  const cashflowsSheet = ss.getSheetByName("Cashflows Input")
  if (cashflowsSheet) {
    saveCashflows();
    ss.deleteSheet(saveCashflows);
  }
}
