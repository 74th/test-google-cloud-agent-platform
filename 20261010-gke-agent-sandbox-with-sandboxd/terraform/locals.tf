locals {
  cluster_name         = var.name_prefix
  vpc_name             = "${var.name_prefix}-vpc"
  subnet_name          = "${var.name_prefix}-subnet"
  router_name          = "${var.name_prefix}-router"
  nat_name             = "${var.name_prefix}-nat"
  registry_name        = "${var.name_prefix}-images"
  system_pool_name     = "${var.short_name_prefix}-system"
  gvisor_pool_name     = "${var.short_name_prefix}-gvisor"
  node_service_account = "${var.short_name_prefix}-node"
  pods_range_name      = "${var.short_name_prefix}-pods"
  services_range_name  = "${var.short_name_prefix}-services"
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  configured_cidrs = {
    primary       = var.network_cidr
    pods          = var.pods_cidr
    services      = var.services_cidr
    control_plane = var.control_plane_cidr
  }
  cidr_start_numbers = {
    for name, range in local.configured_cidrs : name => sum([
      for index, octet in split(".", cidrhost(range, 0)) :
      tonumber(octet) * pow(256, 3 - index)
    ])
  }
  cidr_end_numbers = {
    for name, range in local.configured_cidrs : name => local.cidr_start_numbers[name] + pow(
      2,
      32 - tonumber(split("/", range)[1])
    ) - 1
  }
}

check "resource_names_fit_api_limits" {
  assert {
    condition = (
      length(local.cluster_name) <= 40 &&
      length(local.vpc_name) <= 63 &&
      length(local.subnet_name) <= 63 &&
      length(local.router_name) <= 63 &&
      length(local.nat_name) <= 63 &&
      length(local.registry_name) <= 63 &&
      length(local.system_pool_name) <= 40 &&
      length(local.gvisor_pool_name) <= 40 &&
      length(local.node_service_account) >= 6 && length(local.node_service_account) <= 30 &&
      length(local.pods_range_name) <= 63 &&
      length(local.services_range_name) <= 63
    )
    error_message = "One or more derived resource names exceed their API length limits; adjust name_prefix or short_name_prefix."
  }
}

check "network_ranges_are_distinct" {
  assert {
    condition = alltrue(flatten([
      for left_name, left_range in local.configured_cidrs : [
        for right_name, right_range in local.configured_cidrs :
        left_name == right_name || (
          local.cidr_start_numbers[left_name] > local.cidr_end_numbers[right_name] ||
          local.cidr_start_numbers[right_name] > local.cidr_end_numbers[left_name]
        )
        if index(keys(local.configured_cidrs), left_name) < index(keys(local.configured_cidrs), right_name)
      ]
    ]))
    error_message = "The primary subnet, Pod, Service, and control-plane ranges must not overlap."
  }
}
