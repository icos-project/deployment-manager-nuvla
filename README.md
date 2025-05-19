# ICOS Agent Deployment Manager with Nuvla driver

This is ICOS Agent Deployment Manager with Nuvla driver. This service connects
to ICOS Controller Job Manager to retrieve application deployment definitions
targeting Cloud and Edge resource available via Nuvla. It then launches the
requested applications on the target resources.

## Building

To build the Deployment Manager, run the following command:

```shell
docker build -t icos/deployment-manager-nuvla .
```

## Running

Documentation for the Deployment Manager is available in the [docs](docs/README.md).
