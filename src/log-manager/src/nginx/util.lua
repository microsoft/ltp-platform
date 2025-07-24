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

local lfs = require "lfs"
local path = require "path"

local function is_path_under_log_dir(log_path)
  local real_path = path.abspath(log_path)
  local remote_log_dir = os.getenv("ARCHIVE_LOG_DIR")

  if string.match(real_path, "^/usr/local/pai/logs/.*") or string.match(real_path, "^"..remote_log_dir.."/.*") then
    return true
  end
  return false
end

local function is_input_validated(input)
  if not string.match(input, "^[%w_%-%.~]+$") then
    return false
  end
  return true
end

-- dir always contains entries . and ..
local function is_directory_empty(directory)
  local count = 0
  for _ in lfs.dir(directory) do
    count = count + 1
    if count > 2 then
      return false
    end
  end
  return true
end

-- Check if journalctl can access the given path
local function can_access_journal(journal_path)
  local cmd = "journalctl --directory=" .. journal_path .. " --list-boots -n 1 >/dev/null 2>&1"
  local success = os.execute(cmd)
  return success == 0 or success == true
end

-- Allowed system log files for security
local allowed_logs = {
  -- Traditional syslog files
  "syslog", 
  "kern.log", 
  "dmesg",
  -- Systemd journal files
  "journal",
  "journal.log",
  "systemd/journal"
}

-- Check if a log filename is in the allowed list (including rotated logs)
-- Function to determine if a log file is a systemd journal
local function is_journal_log(filename)
  return string.match(filename, "^journal$") or 
         string.match(filename, "^journal/") or
         string.match(filename, "^systemd/journal") or
         string.match(filename, "^systemd%-journal$") or
         string.match(filename, "^journal%-.*$") -- For service-specific journal logs
end

-- Get the path to the mounted journal logs directory
local function get_journal_path()
  -- List of paths to check in order of preference
  local paths_to_check = {
    "/usr/local/node/log/journal"      -- Primary custom mount path
  }
  
  -- Check each path and return the first valid directory
  for _, path in ipairs(paths_to_check) do
    local attr = lfs.attributes(path)
    if attr and attr.mode == "directory" then
      -- Check if there are actual journal files in this directory
      local has_files = false
      for _ in lfs.dir(path) do
        has_files = true
        break
      end
      
      if has_files then
        return path
      end
    end
  end
  
  -- If no valid path found, return the primary path anyway
  -- journalctl will handle the error if it doesn't exist
  return "/usr/local/node/log/journal"
end

local function is_allowed_log(filename)
  -- Check standard log files and their rotated versions
  for _, allowed in ipairs(allowed_logs) do
    if filename == allowed or 
       string.match(filename, "^" .. allowed .. "%.%d+$") or
       string.match(filename, "^" .. allowed .. "%.%d+%.gz$") then
      return true
    end
  end
  
  -- Special handling for systemd journal files
  if is_journal_log(filename) or
     string.match(filename, "^journal/[^/]*$") or
     string.match(filename, "^journal%-[^/]*$") then
    return true
  end
  
  return false
end

-- Export all utility functions
return {
  is_path_under_log_dir = is_path_under_log_dir,
  is_input_validated = is_input_validated,
  is_directory_empty = is_directory_empty,
  allowed_logs = allowed_logs,
  is_allowed_log = is_allowed_log,
  is_journal_log = is_journal_log,
  get_journal_path = get_journal_path,
  can_access_journal = can_access_journal
}

