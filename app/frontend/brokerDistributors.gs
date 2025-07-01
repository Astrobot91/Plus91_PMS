function showManagementSidebar() {
  const html = HtmlService.createTemplateFromFile('brokerDistributorsHTML')
    .evaluate()
    .setTitle('Manage Brokers and Distributors')
    .setSandboxMode(HtmlService.SandboxMode.IFRAME);
  SpreadsheetApp.getUi().showSidebar(html);
}

function getItemsFromBackend(section) {
  if (section === "Brokers") return getBrokersList();
  else if (section === "Distributors") return getDistributorsList();
  throw new Error("Unknown section: " + section);
}

function getBrokersList() {
  const url = "http://15.207.59.232:8000/brokers";
  const options = { muteHttpExceptions: true, headers: { "Accept": "application/json" } };
  let resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() === 200) {
    let data = JSON.parse(resp.getContentText());
    return data.map(b => b.broker_name);
  }
  throw new Error("Failed to fetch brokers: " + resp.getContentText());
}

function getDistributorsList() {
  const url = "http://15.207.59.232:8000/distributors";
  const options = { muteHttpExceptions: true, headers: { "Accept": "application/json" } };
  let resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() === 200) {
    let data = JSON.parse(resp.getContentText());
    return data.map(d => d.name);
  }
  throw new Error("Failed to fetch distributors: " + resp.getContentText());
}

function addNewItemToBackend(section, newItem) {
  let endpoint;
  if (section === "Brokers") endpoint = "brokers/add";
  else if (section === "Distributors") endpoint = "distributors/add";
  else throw new Error("Unknown section: " + section);
  
  const url = "http://15.207.59.232:8000/" + endpoint;
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ value: newItem }),
    muteHttpExceptions: true
  };
  let resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() !== 200) throw new Error(resp.getContentText());
}

function updateItemInBackend(section, oldItem, newItem) {
  let endpoint;
  if (section === "Brokers") endpoint = "brokers/update";
  else if (section === "Distributors") endpoint = "distributors/update";
  else throw new Error("Unknown section: " + section);
  
  const url = "http://15.207.59.232:8000/" + endpoint;
  const options = {
    method: "put",
    contentType: "application/json",
    payload: JSON.stringify({ old_value: oldItem, new_value: newItem }),
    muteHttpExceptions: true
  };
  let resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() !== 200) throw new Error(resp.getContentText());
}

function deleteItemFromBackend(section, item) {
  let endpoint;
  if (section === "Brokers") endpoint = "brokers/delete";
  else if (section === "Distributors") endpoint = "distributors/delete";
  else throw new Error("Unknown section: " + section);
  
  const url = "http://15.207.59.232:8000/" + endpoint;
  const options = {
    method: "delete",
    contentType: "application/json",
    payload: JSON.stringify({ value: item }),
    muteHttpExceptions: true
  };
  let resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() !== 200) throw new Error(resp.getContentText());
}
