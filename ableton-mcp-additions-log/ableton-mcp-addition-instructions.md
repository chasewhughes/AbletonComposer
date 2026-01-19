# Instructions to add functioanlity to Ableton MCP

  New Clean Structure:

  Source (edit here):
    /Users/chasehughes/ableton-mcp-extended/AbletonMCP_Remote_Script/__init__.py

  Deploy to (via ./deploy.sh):
    ~/Music/Ableton/User Library/MIDI Remote Scripts/AbletonMCP/__init__.py

  Notes:
  Ableton Live Trial version only looks in the App Bundle, not the User Library.

  I've:
  1. ✓ Restored the script to the App Bundle
  2. ✓ Updated deploy.sh to deploy to the App Bundle

  Restart Ableton and you should see AbletonMCP in Control Surfaces again.

  Note: When you upgrade to the full version of Ableton Live (non-Trial), the User Library location will work and you won't need to re-deploy after updates.