"""
Test Controller Detection
Simple script to check if your game controller is detected by pygame
Run this before using ps5_bot_controller.py
"""

import pygame
import sys

def main():
    print("=" * 60)
    print("Game Controller Detection Test")
    print("=" * 60)
    
    try:
        # Initialize pygame
        print("\n⏳ Initializing pygame...")
        pygame.init()
        pygame.joystick.init()
        
        # Check for controllers
        joystick_count = pygame.joystick.get_count()
        print(f"✅ Pygame initialized")
        print(f"📊 Controllers found: {joystick_count}")
        
        if joystick_count == 0:
            print("\n❌ No controllers detected!")
            print("\nTroubleshooting:")
            print("  1. Make sure controller is connected (USB or Bluetooth)")
            print("  2. Check if controller is turned on")
            print("  3. Try unplugging and reconnecting")
            print("  4. On Linux, you may need: sudo usermod -a -G input $USER")
            return
        
        # Display info for each controller
        for i in range(joystick_count):
            print(f"\n{'=' * 60}")
            print(f"Controller {i}:")
            print(f"{'=' * 60}")
            
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            
            print(f"  Name: {joystick.get_name()}")
            print(f"  ID: {joystick.get_id()}")
            print(f"  Axes: {joystick.get_numaxes()}")
            print(f"  Buttons: {joystick.get_numbuttons()}")
            print(f"  Hats (D-pads): {joystick.get_numhats()}")
            
            # Check if it has GUID
            try:
                guid = joystick.get_guid()
                print(f"  GUID: {guid}")
            except:
                pass
        
        # Interactive test mode
        print("\n" + "=" * 60)
        print("INTERACTIVE TEST MODE")
        print("=" * 60)
        print("\nPress buttons and move sticks on your controller.")
        print("You should see the input values change below.")
        print("Press Ctrl+C to exit.\n")
        
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        
        try:
            while True:
                pygame.event.pump()
                
                # Build status line
                status = []
                
                # Axes
                axes_str = "Axes: "
                for i in range(joystick.get_numaxes()):
                    value = joystick.get_axis(i)
                    axes_str += f"{i}:{value:+.2f} "
                status.append(axes_str)
                
                # Buttons
                buttons_pressed = []
                for i in range(joystick.get_numbuttons()):
                    if joystick.get_button(i):
                        buttons_pressed.append(str(i))
                
                if buttons_pressed:
                    status.append(f"Buttons: {','.join(buttons_pressed)}")
                else:
                    status.append("Buttons: None")
                
                # Hats (D-pad)
                if joystick.get_numhats() > 0:
                    hat = joystick.get_hat(0)
                    status.append(f"D-pad: {hat}")
                
                # Print status (overwrite previous line)
                print("\r" + " | ".join(status) + "    ", end="", flush=True)
                
                pygame.time.wait(50)  # 20 Hz update rate
        
        except KeyboardInterrupt:
            print("\n\n✅ Test complete!")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure pygame is installed:")
        print("  pip install pygame")
    
    finally:
        try:
            pygame.joystick.quit()
            pygame.quit()
        except:
            pass

if __name__ == "__main__":
    main()
