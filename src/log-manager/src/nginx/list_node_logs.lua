-- Copyright (c) Microsoft Corporation
-- All rights reserved.
-- MIT License
-- Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
-- documentation files (the "Software"), to deal in the Software without restriction, including without limitation
-- the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
-- to permit persons to whom the Software is furnished to do so, subject to the following conditions:
-- The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
-- THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
-- BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
-- NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
-- DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


--  New API endpoints:
--  - GET /api/v1/node-logs - List available system logs


local cjson = require "cjson"
local lfs = require "lfs"
local util = require "util"

-- Use allowed_logs from util.lua
local allowed_logs = util.allowed_logs

local args = ngx.req.get_uri_args()
local token = args["token"]
local node_name = os.getenv("NODE_NAME") or "unknown"

ngx.log(ngx.INFO, node_name)

if not token then
  ngx.log(ngx.ERR, "token parameter is required")
  ngx.status = ngx.HTTP_BAD_REQUEST
  return ngx.exit(ngx.HTTP_OK)
end

local log_dir = "/usr/local/node/log"
local api_prefix = "/api/v1/node-logs/"
local ret = {}

-- Check if journalctl is available
local journalctl_available = os.execute("which journalctl >/dev/null 2>&1")
local journal_path = util.get_journal_path()

ngx.log(ngx.INFO, "Using journal path: " .. journal_path)

if journalctl_available then
  -- Check if the journal path exists and is accessible with journalctl
  local journal_attr = lfs.attributes(journal_path)
  local can_access = util.can_access_journal(journal_path)
  
  ngx.log(ngx.INFO, "Journal path accessible: " .. tostring(can_access))
  
  if journal_attr and journal_attr.mode == "directory" and can_access then
    -- Add general journal entry
    ret["journal"] = {
      url = api_prefix .. "journal?token=" .. token .. "&node=" .. node_name,
      description = "System Journal (all entries from " .. journal_path .. ")",
      type = "journal"
    }
    
    -- Check available systemd services for specific journal logs
    -- Use the custom path for journalctl
    local handle = io.popen("journalctl --directory=" .. journal_path .. " --field=_SYSTEMD_UNIT 2>/dev/null | sort | uniq")
    if handle then
      local services = handle:read("*a")
      handle:close()
      
      -- Add specific services
      for service in services:gmatch("([^\n]+)") do
        if service and service ~= "" then
          -- Skip some very common services to avoid clutter
          if not string.match(service, "^session") and
             not string.match(service, "^user") and
             not string.match(service, "^scope") then
            ret["journal-" .. service] = {
              url = api_prefix .. "journal-" .. service .. "?token=" .. token .. "&node=" .. node_name,
              description = "Journal for service: " .. service,
              type = "journal"
            }
          end
        end
      end
    else
      -- Fallback to static list of common services if journalctl command failed
      ngx.log(ngx.WARN, "Failed to get systemd units, falling back to static list")
      local common_services = {"docker", "kubelet", "containerd", "ssh", "systemd", "ntpd", "sshd"}
      for _, service in ipairs(common_services) do
        ret["journal-" .. service] = {
          url = api_prefix .. "journal-" .. service .. "?token=" .. token .. "&node=" .. node_name,
          description = "Journal for service: " .. service,
          type = "journal"
        }
      end
    end
  else
    ngx.log(ngx.WARN, "Journal directory not found: " .. journal_path)
  end
end

-- Check each allowed log file
for _, log_name in ipairs(allowed_logs) do
  local log_path = log_dir .. "/" .. log_name
  local attr = lfs.attributes(log_path)
  
  if attr and attr.mode == "file" then
    -- Add current log file
    ret[log_name] = {
      url = api_prefix .. log_name .. "?token=" .. token .. "&node=" .. node_name,
      size = attr.size,
      modified = attr.modification
    }
    
    -- Check for rotated logs (syslog.1, syslog.2, etc.)
    for i = 1, 10 do
      local rotated_path = log_path .. "." .. i
      local rotated_attr = lfs.attributes(rotated_path)
      if rotated_attr and rotated_attr.mode == "file" then
        ret[log_name .. "." .. i] = {
          url = api_prefix .. log_name .. "." .. i .. "?token=" .. token .. "&node=" .. node_name,
          size = rotated_attr.size,
          modified = rotated_attr.modification
        }
      end
    end
    
    -- Check for compressed rotated logs (.gz)
    for i = 1, 10 do
      local gz_path = log_path .. "." .. i .. ".gz"
      local gz_attr = lfs.attributes(gz_path)
      if gz_attr and gz_attr.mode == "file" then
        ret[log_name .. "." .. i .. ".gz"] = {
          url = api_prefix .. log_name .. "." .. i .. ".gz" .. "?token=" .. token .. "&node=" .. node_name,
          size = gz_attr.size,
          modified = gz_attr.modification,
          compressed = true
        }
      end
    end
  end
end

-- Add node metadata
ret["_metadata"] = {
  node_name = node_name,
  timestamp = ngx.time(),
  log_directory = log_dir
}

ngx.say(cjson.encode(ret))
