const CHART_INDEX_URL = "https://reanahub.github.io/reana/index.yaml";

function fillTable(releases) {
  tableBody = document.getElementById("tableBody");
  releases.forEach((release) => {
    const row = document.createElement("tr");
    const versionCell = document.createElement("td");
    const versionLink = document.createElement("a");
    versionLink.title = release.version;
    versionLink.href = release.urls[0];
    const versionText = document.createTextNode(release.version);
    versionLink.appendChild(versionText);
    versionCell.appendChild(versionLink);
    row.appendChild(versionCell);

    const createdCell = document.createElement("td");
    const createdDate = new Date(release.created);
    const createdText = document.createTextNode(createdDate.toISOString());
    createdCell.appendChild(createdText);
    row.appendChild(createdCell);

    tableBody.appendChild(row);
  });
}

async function fetchIndex(url) {
  const response = await fetch(url)
    .then((res) => res.text())
    .catch((error) => {
      console.error("Error while fetching index.yaml:", error);
    });
  try {
    const indexFile = jsyaml.safeLoad(response);
    fillTable(indexFile.entries.reana);
  } catch (error) {
    console.log("Error while parsing index.yaml:", error);
  }
}

fetchIndex(CHART_INDEX_URL);
