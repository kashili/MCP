# Initial Setup

This README will guide you through the various steps to execute terraform scripts on your local machine. Afterwards, you will deploy an app to Azure's Web App service using the Azure CLI.

## Install Terraform

1. Navigate to [terraform installation](https://developer.hashicorp.com/terraform/tutorials/azure-get-started/install-cli) page.
   1. Scroll down.
2. Select `Manual installation`.
3. Select `Pre-compiled executable`.
4. Click the `appropriate zip archive` link.
5. Select the binary download appropriate for your system.
6. Once the download is complete, unzip the downloaded folder.*Keep this window pane open.*
7. Create a folder in your filesystem (somewhere on your machine) called `terraform`.*We will point a System Environment Variable to this newly created folder, so make sure its location is memorable.*
8. From the unzipped folder, drag and drop the `terraform.exe` application into the newly created `terraform` folder.
9. Navigate to your system's Environment Variables.
10. Add a new PATH variable, pointing to the newly created `terraform` folder -- which should now contain a single file: `terraform.exe`.
11. Save these changes and close/exit any windows opened during this installation process.
12. Confirm terraform is installed:
    1. Navigate to any CLI on your machine.
    2. Enter `terraform -help` to confirm if terraform was installed correctly.

## Install the Azure CLI

1. Navigate to [How to install the Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest).
2. Follow all on-screen instructions for your specific OS.
3. After installation, enter `az help` to confirm if the Azure CLI was installed correctly.

## Set secrets inside `terraform.tfvars`

1. Navigate to the `terraform` directory.
2. Create a copy of the `terraform.tfvars.example` file, name this copy `terraform.tfvars`.
3. Edit the dummy variables with actual values:
   1. Atlassian Domain
   2. Atlassian Email
   3. Atlassian API Token
   4. Project Key

You are now ready to begin application deployment.

# Deployment

## Azure CLI Commands for Manual Deployment

If you want to test app deployment **WITHOUT** terraform, use the following commands:

1. Create an Azure Resource Group, Web App, and App Plan. This single command:
   1. Creates resource group `mcp-rg` (if it doesn't exist).
   2. Creates an App Service plan (B1 tier).
   3. Creates the web app.
   4. Zips and uploads your code.
   5. Installs dependencies from `requirements.txt`.

`az webapp up --name mcpprojectmanager --resource-group mcp-rg --runtime "PYTHON:3.11" --sku B1 --location centralus`

2. Set the start-up command:

`az webapp config set --name mcpprojectmanager --resource-group mcp-rg --startup-file "gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"`

3. Set the environment variables, after editing the example values:

`az webapp config appsettings set --name mcpprojectmanager --resource-group mcp-rg --settings ATLASSIAN_DOMAIN="YOUR_SECRET_HERE" ATLASSIAN_EMAIL="YOUR_SECRET_HERE" ATLASSIAN_API_TOKEN="YOUR_SECRET_HERE" JIRA_PROJECT_KEY="YOUR_SECRET_HERE" JIRA_DEADLINE="2026-06-30" JIRA_HOURS_PER_WEEK="40"`

4. Finally, navigate to: [https://mcpprojectmanager.azurewebsites.net]().

## Terraform Commands for Semi-automatic Deployment

### App Deployment

To create the app from scratch (i.e. the resources do not already exist on Azure):

1. Navigate to the terraform directory:
   `cd terraform
   `
2. Initialize the terraform service:
   `terraform init
   `
3. Preview resource creation:
   `terraform plan
   `
4. Create resources (without additional user confirmation):
   `terraform apply -auto-approve
   `
5. Navigate back to the root directory:
   `cd ..
   `
6. Create a Zip file of the root directory:

   Windows:
   `Compress-Archive -Path (Get-ChildItem -Exclude terraform, .git, .terraform, .venv, __pycache__, *.pyc).FullName -DestinationPath app.zip -Force
   `
   Unix:
   `zip -r app.zip .
   `
7. Deploy the app (zip file) to Azure Web Apps:
   `az webapp deploy --resource-group mcp-rg --name mcpprojectmanager --src-path app.zip --type zip
   `
8. Visit the app at: [https://mcpprojectmanager.azurewebsites.net]()

### Teardown

To tear-down the app, and assoicated resources created by the above:
`terraform destroy`

### Troubleshooting

1. If the above deployment command errors-out or times-out, use the following command as a fallback:
   `az webapp up --name mcpprojectmanager --resource-group mcp-rg --plan mcpprojectmanager-plan`

   The `az webapp up` will likely continue to say `Starting the site...` for multiple minutes, when in-reality, the app has already started.

   Please navigate to the app's URL after about 5 minutes of `Starting the site...` to confirm the app has been deployed or not.

   `az webapp up` can be cancelled after user's confirmation of app deployment, otherwise `az webapp up` will time-out after 10 minutes.
2. To update the app after codebase changes, use the same command as described in Step 7 above.

## Register Additional Azure Providers for Terraform (if needed)

**FOLLOW THESE STEPS FOR BRAND-NEW SUBSCRIPTIONS ONLY.
TYLER HAS ALREADY RUN THESE COMMANDS FOR THE CURRENT SUBSCRIPTION. PLEASE IGNORE.**

1. Navigate to `terraform/provider_registration.ps1`.
2. Add any Azure Providers that need to be registered.
3. Ensure to uncomment the registration command.
4. Run the `provider_registration.ps1` pwsh file.
5. Confirm each provider is registered.
