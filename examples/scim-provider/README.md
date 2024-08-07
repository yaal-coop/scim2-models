# scim-provider

An example WSGI-SCIM provider using scim2-models. It utilizes [werkzeug](https://werkzeug.palletsprojects.com/) and [scim2-filter-parser](https://github.com/15five/scim2-filter-parser).

The provider keeps all resources in-memory, they are lost once the process exits.

## Usage

```shell
$ scim-provider [-h] [--schema SCHEMA] [--resource-type RESOURCE_TYPE] [--bearer-token BEARER_TOKEN] [--hostname HOSTNAME] [--port PORT] [--reverse-proxy] [--dump-resources DUMP_RESOURCES]
```

- `-h`/`--help`: Show help message
- `--reverse-proxy`: Allow using the provider behind a Reverse Proxy (required for URL rewriting).
- `--schema`: Register schemas from specified JSON file. If not provided, loads the default schemas from RFC 7643.
- `--resource-type`: Register resource types from specified JSON file. If not provided, loads the default resource types from RFC 7643.
- `--bearer-token`: Registers a bearer token that can be used for accessing the service. If no tokens are provided, anonymous access without authentication is allowed.
- `--hostname`: The hostname to listen on. Defaults to `127.0.0.1`.
- `--port`: The port to listen on. Defaults to `8080`.
- `--dump-resources`: Dump a JSON document containing all resources when the provider exits normally.

## Notes

This provider can be used as a starting point if you want to implement a SCIM provider. You should probably change the following things, if you want to use it in production:

- Use a proper production WSGI server instead of the one provided by Werkzeug
- Implement your own Backend as a subclass of `scim_provider.backend.Backend`
- Implement proper authorization with OAuth instead of public access or static bearer tokens
- Support the `/Me` endpoint, if it applies to your use case
- Add support for using either a static URL prefix or improve the support for usage behind a reverse proxy

The provider in its current state has been tested successfully against a live Microsoft Entra system.
