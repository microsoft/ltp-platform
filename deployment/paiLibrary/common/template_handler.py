# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import jinja2
import logging
import logging.config
import os


logger = logging.getLogger(__name__)

def generate_from_template_dict(template_data, map_table):
    """
    Generate content from template using Jinja2 with lookup function support.
    
    Args:
        template_data: The template string content
        map_table: Dictionary containing variables for template rendering
        
    Returns:
        Rendered template content
    """
    generated_file = None
    if 'lookup' not in template_data:
        generated_file = jinja2.Template(template_data).render(
            map_table
        )
    else:
        # Create a Jinja2 environment with FileSystemLoader to support lookup function
        # Use the current working directory as the base path for file lookups
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.getcwd()),
            undefined=jinja2.StrictUndefined
        )
        
        # Add lookup function to the environment
        def lookup_function(name, path):
            """Custom lookup function to read files"""
            try:
                with open(path, 'r') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to read file {path}: {e}")
                logger.warning(f"Current working directory: {os.getcwd()}")
                return f"# Error reading file {path}: {e}"
        
        env.globals['lookup'] = lookup_function
        
        # Create template from the provided template data
        template = env.from_string(template_data)
        
        # Render the template with the provided variables
        generated_file = template.render(map_table)
    
    return generated_file
