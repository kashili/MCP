# This script registers the required Azure providers for the Terraform deployment.

# List of required Azure providers for the Terraform deployment. 
# You can add more providers to this list if needed.
$providers = @(
    # Add any additional providers below, if needed, followed by a comma.
    "Microsoft.Devices",
    "Microsoft.DBforMySQL",
    "Microsoft.HealthcareApis",
    "Microsoft.Storage",
    "Microsoft.DataMigration",
    "Microsoft.GuestConfiguration",
    "Microsoft.Search",
    "Microsoft.DataLakeStore",
    "Microsoft.Cdn",
    "Microsoft.OperationalInsights",
    "Microsoft.ContainerInstance",
    "Microsoft.EventGrid",
    "Microsoft.DesktopVirtualization",
    "Microsoft.SignalRService",
    "Microsoft.Relay",
    "Microsoft.AppConfiguration",
    "Microsoft.Network",
    "Microsoft.Blueprint",
    "Microsoft.Web"
)

foreach ($p in $providers) {
    # UNCOMMENT the below line to register a provider if not already registered. It may take few minutes to register the provider.
    # az provider register --namespace $p

    # Check the registration status of the provider. It should be "Registered".
    az provider show --namespace $p --query registrationState -o tsv
}