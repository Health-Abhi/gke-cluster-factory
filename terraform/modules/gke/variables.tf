variable "project_id" { type = string }
variable "cluster_name" { type = string }
variable "region" { type = string }
variable "node_locations" { type = list(string) }
variable "network_self_link" { type = string }
variable "subnetwork_self_link" { type = string }
variable "pod_range_name" { type = string }
variable "service_range_name" { type = string }
variable "control_plane_cidr" { type = string }
variable "private_endpoint_only" { type = bool }
variable "authorized_cidrs" { type = list(string) }
variable "release_channel" { type = string }
variable "deletion_protection" { type = bool }
variable "owner_group" { type = string }
variable "platform_admin_group" { type = string }
variable "gke_security_group" { type = string }
variable "labels" { type = map(string) }
variable "max_pods_per_node" { type = number }
variable "system_machine_type" { type = string }
variable "general_machine_type" { type = string }
variable "system_min_nodes" { type = number }
variable "system_max_nodes" { type = number }
variable "general_min_nodes" { type = number }
variable "general_max_nodes" { type = number }
variable "gpu" {
  type = object({
    enabled            = bool
    model              = optional(string)
    machine_type       = optional(string)
    accelerator_count  = number
    minimum_nodes      = number
    maximum_nodes      = number
    zones              = list(string)
    provisioning_model = string
    reservation_name   = optional(string)
  })
}
