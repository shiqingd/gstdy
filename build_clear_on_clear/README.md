Docker container to build our kernel on Clear Linux.

# Before Running

Add SSH private and public keys to the directory. I used `sys_oak`'s
credentials; you can use those as well (from `~/.ssh/`) or your own
authorized kernels.

# Build

`make build` will create a Docker container called `clear`.

# Running

`make run` will run the Docker container and place the built kernel inside
the `artifacts` directory.

# Issues

When I actually run this in Jenkins, I need a way of passing the build number to
the Docker container. It'll be set as an environment variable, same as Jenkins.
